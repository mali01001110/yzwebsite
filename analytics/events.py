"""
The server-side API other apps use to emit analytics.

``track_event`` is the whole public surface. Views and DRF viewsets call it and
never touch the models, which is what keeps the rest of the project free of
imports from this app: deleting ``analytics`` leaves one broken import in one
place rather than model references scattered through the codebase.

Also here: deterministic A/B assignment. The variant is computed by hashing
``visitor_id + experiment_key``, so the same visitor always sees the same
variant with no database read on the request path. The
``ExperimentAssignment`` row exists to make the split auditable and joinable,
not to decide anything.
"""
from __future__ import annotations

import hashlib
import logging
import time
from decimal import Decimal
from typing import Any, Sequence

from django.http import HttpRequest

from .buffer import KIND_EVENT, KIND_SEARCH, record
from .defaults import get_setting
from .privacy import hash_visitor, scrub, scrub_props
from .client_ip import get_client_ip

logger = logging.getLogger(__name__)


def track_event(
    request_or_session: HttpRequest | Any,
    name: str,
    props: dict[str, Any] | None = None,
    value: Decimal | float | None = None,
) -> bool:
    """
    Queue a named event. Returns whether it was accepted.

    Never raises and never writes to the database: like everything else on the
    request path, it appends to the buffer and returns. A caller in a view can
    treat it as fire-and-forget.

    ``request_or_session`` accepts either an ``HttpRequest`` (the common case,
    from a view) or an existing ``Session`` instance (from the pipeline, where
    no request exists).
    """
    if not get_setting('ENABLED'):
        return False

    if name not in get_setting('EVENT_ALLOWLIST'):
        # Unknown names are refused rather than stored, so a typo in a view
        # cannot silently create a metric nobody is reading, and a compromised
        # client cannot inflate name cardinality without bound.
        logger.warning('Rejected analytics event with unregistered name %r', name)
        return False

    try:
        payload = _payload_for(request_or_session)
    except Exception:
        logger.exception('Could not resolve analytics context for event %r', name)
        return False

    record(
        KIND_EVENT,
        name=name,
        props=scrub_props(props or {}),
        value=Decimal(str(value)) if value is not None else None,
        occurred_at=time.time(),
        **payload,
    )
    return True


def track_search(
    request: HttpRequest,
    query: str,
    result_count: int,
    clicked_result: bool = False,
) -> bool:
    """
    Record an internal site search.

    Zero-result queries are the most actionable thing this system collects: a
    list, in visitors' own words, of what they expected to find and did not.
    The site has no search box yet, so this exists ready for one.
    """
    if not get_setting('ENABLED'):
        return False

    record(
        KIND_SEARCH,
        query=scrub(query, max_length=200),
        result_count=max(int(result_count), 0),
        clicked_result=bool(clicked_result),
        occurred_at=time.time(),
    )
    return True


def assign_variant(
    visitor_id: str,
    experiment_key: str,
    variants: Sequence[str] = ('control', 'treatment'),
) -> str:
    """
    Return this visitor's variant, computed rather than looked up.

    Hashing ``visitor_id + experiment_key`` makes assignment stable across
    requests and processes with no state and no query. Including the key means
    a visitor in the control group of one experiment is not systematically in
    the control group of every other one.
    """
    if not variants:
        raise ValueError('assign_variant needs at least one variant')

    digest = hashlib.sha256(f'{visitor_id}:{experiment_key}'.encode()).digest()
    # First 8 bytes is far more entropy than the bucket count needs, and using
    # an integer avoids any modulo bias worth worrying about at this scale.
    bucket = int.from_bytes(digest[:8], 'big') % len(variants)
    return variants[bucket]


def persist_assignment(visitor, experiment_key: str, variant: str):
    """
    Write the assignment row, once per visitor per experiment.

    Called at most once per visitor per experiment, from a view that has
    already computed the variant. Returns the row.
    """
    from django.utils import timezone

    from .models import ExperimentAssignment

    assignment, _ = ExperimentAssignment.objects.get_or_create(
        visitor=visitor,
        experiment_key=experiment_key[:ExperimentAssignment.KEY_MAX_LENGTH],
        defaults={
            'variant': variant[:ExperimentAssignment.VARIANT_MAX_LENGTH],
            'assigned_at': timezone.now(),
        },
    )
    return assignment


def visitor_id_for(request: HttpRequest) -> str:
    """Return the rotating visitor identifier for a live request."""
    return hash_visitor(
        get_client_ip(request), request.META.get('HTTP_USER_AGENT', '')
    )


def _payload_for(request_or_session: HttpRequest | Any) -> dict[str, Any]:
    """Build the visitor/session context an event needs to be attributable."""
    if hasattr(request_or_session, 'META'):
        request = request_or_session
        user = getattr(request, 'user', None)
        return {
            'visitor_id': visitor_id_for(request),
            'ip_address': get_client_ip(request),
            'ip_hash': '',
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:400],
            'user_id': user.pk if user is not None and user.is_authenticated else None,
            'path': request.path[:200],
            'country_hint': '',
            'params': {},
            'referrer_host': '',
            'referrer_url': '',
            'language': '',
        }

    # A Session instance: the visitor already exists, so the pipeline can
    # attach the event without recomputing anything.
    session = request_or_session
    return {
        'visitor_id': session.visitor.visitor_id,
        'ip_address': None,
        'ip_hash': session.ip_hash,
        'user_agent': '',
        'user_id': session.visitor.user_id,
        'path': session.exit_path or session.landing_path,
        'country_hint': session.country,
        'params': {},
        'referrer_host': session.referrer_host,
        'referrer_url': session.referrer_url,
        'language': session.language,
    }
