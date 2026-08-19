"""
The beacon ingest endpoint.

One route, one method, one job: accept a batch, validate it, push it to the
buffer, return 204. Nothing is processed inline — the response goes back before
any enrichment or database work happens, because the browser is often sending
this from ``visibilitychange`` while the page is being torn down and every
millisecond of latency is a chance the request never completes.

CSRF is exempted because ``navigator.sendBeacon`` cannot attach a token and
cannot read a cookie-setting response. The replacement control is an origin
check against the project's own ``CORS_ALLOWED_ORIGINS`` and ``ALLOWED_HOSTS``,
which is what actually matters here: there is no authenticated state to forge,
so the risk is not CSRF but a third-party page writing junk into the dataset.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import consent
from .buffer import KIND_EVENT, KIND_PAGEVIEW, record
from .client_ip import get_client_ip
from .defaults import get_setting
from .geo import country_from_meta
from .privacy import hash_ip, hash_visitor, safe_referrer
from .serializers import EventBatchSerializer
from .throttling import IngestRateThrottle
from .useragent import client_hints_from_meta

logger = logging.getLogger(__name__)

# Events that describe a view of a page or section become PageView rows; the
# rest become Event rows. Keeping the split here rather than in the pipeline
# means the buffer carries records already destined for the right table.
PAGEVIEW_EVENT_NAMES = frozenset({'pageview', 'section_view'})


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([IngestRateThrottle])
def ingest_events(request):
    """
    Accept a batch of beacon events.

    Always returns 204 on success with no body: the client uses sendBeacon and
    cannot read a response, so returning anything is wasted bytes on a request
    that fires during page unload.
    """
    if not get_setting('ENABLED'):
        return Response(status=status.HTTP_204_NO_CONTENT)

    if not _origin_is_allowed(request):
        # 403 rather than 204: a browser cannot see either, but a misconfigured
        # deployment showing up in the access log as 403 is diagnosable, where
        # a silent 204 would look like everything was working.
        return Response(
            {'detail': 'Origin not allowed.'}, status=status.HTTP_403_FORBIDDEN
        )

    if _body_too_large(request):
        return Response(
            {'detail': 'Payload too large.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # Accepted and discarded, deliberately. Returning an error would let a page
    # detect the consent state by probing, and there is nothing the client
    # could usefully do about it either way.
    #
    # Note this is not gated on REQUIRE_CONSENT: a DNT or Sec-GPC signal is a
    # hard opt-out from Tier 2 whether or not consent gating is switched on,
    # and ConsentState already folds both in.
    consent_state = getattr(request, 'analytics_consent', None) or consent.read(request)
    if not consent_state.allows_tier_two:
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = EventBatchSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    _enqueue(request, serializer.validated_data)
    return Response(status=status.HTTP_204_NO_CONTENT)


def _enqueue(request, payload: dict) -> None:
    """Turn a validated batch into buffered records."""
    meta = request.META
    ip_address = get_client_ip(request)
    user_agent = meta.get('HTTP_USER_AGENT', '')
    referrer_host, referrer_url = safe_referrer(meta.get('HTTP_REFERER'))
    user = getattr(request, 'user', None)

    shared = {
        'visitor_id': hash_visitor(ip_address, user_agent),
        'ip_hash': hash_ip(ip_address),
        'ip_address': ip_address,
        'user_agent': user_agent[:400],
        'client_hints': client_hints_from_meta(meta),
        'country_hint': country_from_meta(meta),
        'language': meta.get('HTTP_ACCEPT_LANGUAGE', '')[:35],
        'referrer_host': referrer_host,
        'referrer_url': referrer_url,
        'params': {},
        'user_id': user.pk if user is not None and user.is_authenticated else None,
    }

    client_context = {
        'screen': _dimension_pair(payload.get('screen_width'), payload.get('screen_height')),
        'viewport': _dimension_pair(payload.get('viewport_width'), payload.get('viewport_height')),
        'dpr': payload.get('pixel_ratio'),
        'tz': payload.get('timezone', ''),
        'connection': payload.get('connection', ''),
    }

    for event in payload['events']:
        name = event['name']
        occurred_at = event.get('t') or time.time()

        if name in PAGEVIEW_EVENT_NAMES:
            record(
                KIND_PAGEVIEW,
                path=event.get('path') or '/',
                title=event.get('title', ''),
                query_hash='',
                status_code=200,
                response_ms=None,
                engaged_seconds=event.get('engaged_seconds'),
                max_scroll_depth=event.get('max_scroll_depth'),
                is_spa_navigation=event.get('is_spa_navigation', True),
                occurred_at=occurred_at,
                **shared,
            )
            continue

        record(
            KIND_EVENT,
            name=name,
            props={**event.get('props', {}), **_compact(client_context)},
            value=event.get('value'),
            occurred_at=occurred_at,
            path=event.get('path') or '/',
            **shared,
        )


def _origin_is_allowed(request) -> bool:
    """
    Check the request's origin against the project's own allowlists.

    Reads ``CORS_ALLOWED_ORIGINS`` and ``ALLOWED_HOSTS`` rather than defining a
    third list, so there is one place to add a domain. A request with no Origin
    header is allowed: sendBeacon from a same-origin page may omit it, and
    non-browser clients are handled by the throttle instead.
    """
    origin = request.META.get('HTTP_ORIGIN')
    if not origin:
        return True

    allowed = {o.rstrip('/') for o in getattr(settings, 'CORS_ALLOWED_ORIGINS', [])}
    if origin.rstrip('/') in allowed:
        return True

    host = (urlsplit(origin).hostname or '').lower()
    return any(
        host == allowed_host.lower().lstrip('.')
        for allowed_host in settings.ALLOWED_HOSTS
        if allowed_host != '*'
    )


def _body_too_large(request) -> bool:
    """
    Reject oversized bodies before DRF parses them.

    CONTENT_LENGTH can be absent or a lie, so this is a cheap first filter and
    not the only limit; the serializer's per-batch and per-event caps are what
    actually bound the work.
    """
    try:
        declared = int(request.META.get('CONTENT_LENGTH') or 0)
    except (TypeError, ValueError):
        return False
    return declared > get_setting('INGEST_MAX_BODY_BYTES')


def _dimension_pair(width: int | None, height: int | None) -> str:
    return f'{width}x{height}' if width and height else ''


def _compact(values: dict) -> dict:
    """Drop empty context keys, so props stay small and readable."""
    return {key: value for key, value in values.items() if value}
