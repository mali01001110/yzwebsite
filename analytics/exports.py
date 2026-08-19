"""
Data-subject request helpers: export everything held about one visitor, or
erase it.

The rotating salt makes these narrower than they look, and the limitation is
worth stating rather than hiding. ``visitor_id`` is derived from a salt that
changes every 24 hours, so a request can only reach the rows recorded under the
identifier supplied. Yesterday's rows carry a different identifier and cannot
be linked to today's — by design, since that unlinkability is the entire reason
the salt rotates.

In practice this means: to answer a request, the identifier has to come from
the visitor's own current session, and the answer covers the current rotation
window. Everything older has already been de-linked from any individual, which
is a stronger privacy position than being able to produce it on demand.
"""
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from .models import (
    Event,
    ExperimentAssignment,
    PageView,
    SearchQuery,
    Session,
    Visitor,
    VisitorIP,
)

logger = logging.getLogger(__name__)


def export_visitor_data(visitor_id: str) -> dict[str, Any]:
    """
    Return every stored row for one visitor, as JSON-serialisable primitives.

    Returns a dict with an empty ``visitor`` key when nothing is held, rather
    than raising: "we hold nothing about you" is a valid and common answer to a
    subject access request.
    """
    visitor = (
        Visitor.objects.filter(visitor_id=visitor_id)
        .prefetch_related('sessions__pageviews', 'sessions__events', 'sessions__searches')
        .first()
    )
    if visitor is None:
        return {'visitor': None, 'sessions': [], 'note': 'No data held for this identifier.'}

    return {
        'visitor': {
            'visitor_id': visitor.visitor_id,
            'first_seen_at': visitor.first_seen_at.isoformat(),
            'last_seen_at': visitor.last_seen_at.isoformat(),
            'is_bot': visitor.is_bot,
            'user_id': visitor.user_id,
            'first_touch': {
                'channel': visitor.first_touch_channel,
                'source': visitor.first_touch_source,
                'campaign': visitor.first_touch_campaign,
            },
            'last_touch': {
                'channel': visitor.last_touch_channel,
                'source': visitor.last_touch_source,
                'campaign': visitor.last_touch_campaign,
            },
        },
        'sessions': [_serialize_session(session) for session in visitor.sessions.all()],
        'note': (
            'The visitor identifier is derived from a salt that rotates every '
            '24 hours. This export covers only the rows recorded under the '
            'identifier supplied; earlier activity carries a different '
            'identifier and cannot be linked to it.'
        ),
    }


def delete_visitor_data(visitor_id: str) -> dict[str, int]:
    """
    Erase everything stored under one visitor identifier.

    Cascades from the ``Visitor`` row, so sessions, pageviews, events, searches
    and experiment assignments all go with it. ``DailyStat`` is untouched: it
    holds no per-visitor rows, only counts that this visitor contributed to,
    and those cannot be attributed back to anyone.
    """
    visitor = Visitor.objects.filter(visitor_id=visitor_id).first()
    if visitor is None:
        return {'visitors': 0}

    session_ids = list(visitor.sessions.values_list('pk', flat=True))

    with transaction.atomic():
        removed = {
            'pageviews': PageView.objects.filter(session_id__in=session_ids).delete()[0],
            'events': Event.objects.filter(session_id__in=session_ids).delete()[0],
            'searches': SearchQuery.objects.filter(session_id__in=session_ids).delete()[0],
            'experiment_assignments': ExperimentAssignment.objects.filter(
                visitor=visitor
            ).delete()[0],
            'sessions': Session.objects.filter(pk__in=session_ids).delete()[0],
            'visitors': Visitor.objects.filter(pk=visitor.pk).delete()[0],
        }

    logger.info('Erased analytics data for visitor %s: %s', visitor_id[:12], removed)
    return removed


def export_ip_data(ip_address: str) -> dict[str, Any]:
    """
    Return the raw-address listing row for one address.

    Only reachable while ``ANALYTICS['STORE_RAW_IPS']`` is on and the row is
    inside its retention window. Unlike :func:`export_visitor_data` this can be
    answered from an address somebody gives you, which is what makes it the
    practical entry point for a subject access request.
    """
    row = VisitorIP.objects.filter(ip_address=ip_address).first()
    if row is None:
        return {'ip_address': ip_address, 'held': False}

    return {
        'ip_address': row.ip_address,
        'held': True,
        'is_public': row.is_public,
        'visit_count': row.visit_count,
        'first_seen_at': row.first_seen_at.isoformat(),
        'last_seen_at': row.last_seen_at.isoformat(),
        'last_path': row.last_path,
        'last_user_agent': row.last_user_agent,
        'country': row.country,
        'is_bot': row.is_bot,
        'note': (
            'This is the only record in which the address appears in the clear. '
            'Session-level rows hold a rotating hash and a truncated network '
            'only, and cannot be traced back to this address.'
        ),
    }


def delete_ip_data(ip_address: str) -> int:
    """
    Erase the raw-address listing row for one address.

    Returns the number of rows removed. Session and pageview rows are
    deliberately untouched: they carry no raw address, so they identify nobody
    once this row is gone, and deleting them would silently corrupt the
    historical counts in ``DailyStat``.
    """
    removed, _ = VisitorIP.objects.filter(ip_address=ip_address).delete()
    if removed:
        logger.info('Erased raw-address record for one visitor')
    return removed


def _serialize_session(session: Session) -> dict[str, Any]:
    return {
        'started_at': session.started_at.isoformat(),
        'ended_at': session.ended_at.isoformat() if session.ended_at else None,
        'landing_path': session.landing_path,
        'exit_path': session.exit_path,
        'channel': session.channel,
        'referrer_host': session.referrer_host,
        'country': session.country,
        'region': session.region,
        'city': session.city,
        'browser': session.browser,
        'os': session.os,
        'device_type': session.device_type,
        'language': session.language,
        # The hash and the truncated network, never a raw address: the raw
        # address was never stored, so it cannot appear in an export either.
        'ip_hash': session.ip_hash,
        'ip_truncated': session.ip_truncated,
        'is_bot': session.is_bot,
        'pageview_count': session.pageview_count,
        'duration_seconds': session.duration_seconds,
        'pageviews': [
            {
                'path': view.path,
                'title': view.title,
                'occurred_at': view.occurred_at.isoformat(),
                'engaged_seconds': view.engaged_seconds,
                'max_scroll_depth': view.max_scroll_depth,
                'status_code': view.status_code,
            }
            for view in session.pageviews.all()
        ],
        'events': [
            {
                'name': event.name,
                'props': event.props,
                'value': str(event.value) if event.value is not None else None,
                'occurred_at': event.occurred_at.isoformat(),
            }
            for event in session.events.all()
        ],
        'searches': [
            {
                'query': search.query,
                'result_count': search.result_count,
                'clicked_result': search.clicked_result,
                'occurred_at': search.occurred_at.isoformat(),
            }
            for search in session.searches.all()
        ],
    }
