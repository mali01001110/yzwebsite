"""
Everything that happens after the request has been served.

One daemon thread owns five jobs: draining the write buffer, enriching what it
drained, closing idle sessions, rolling yesterday's raw rows into ``DailyStat``,
and deleting raw rows past their retention window.

Each job is also a management command, and the thread is disabled with
``ANALYTICS['RUN_INLINE_SCHEDULER'] = False``, so moving this work to Render
Cron, GitHub Actions or a real worker later is a settings change rather than a
rewrite. See ``docs/adr/0001-first-party-analytics-pipeline.md``.

Every job is idempotent and safe to run concurrently. Concurrency safety comes
from a Postgres advisory lock rather than from a row-level lock, because the
jobs span whole tables and an advisory lock is free when uncontended. A second
process that cannot take the lock skips the run rather than waiting: the work
is periodic, so the next tick will pick it up.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from django.db import connection, transaction
from django.db.models import Count, F, Max, Min, Q, Sum
from django.utils import timezone as django_timezone

from .client_ip import is_public_ip

from .buffer import (
    KIND_EVENT,
    KIND_PAGEVIEW,
    KIND_SEARCH,
    KIND_SECURITY,
    buffer,
)
from .defaults import get_setting
from .geo import lookup as geo_lookup
from .models import (
    DailyStat,
    Event,
    PageView,
    SearchQuery,
    SecurityEvent,
    Session,
    Visitor,
    VisitorIP,
)
from .privacy import truncate_ip
from .useragent import parse as parse_user_agent

logger = logging.getLogger(__name__)

# Arbitrary but fixed: two processes must derive the same number to contend for
# the same lock. Derived from the app name so it cannot collide with a lock
# some other part of the project takes.
ADVISORY_LOCK_KEY = 8_531_207

_scheduler_thread: threading.Thread | None = None
_scheduler_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Flush: buffer -> database
# ---------------------------------------------------------------------------

def flush() -> int:
    """
    Drain the buffer and write everything in it. Returns the row count written.

    Enrichment happens here rather than in the middleware: the geo lookup, the
    user-agent parse and the bot scoring are all too slow for the request path
    and none of them is needed to serve the page.
    """
    records = buffer.drain()
    if not records:
        return 0

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        grouped[item.get('kind', '')].append(item)

    written = 0
    try:
        with transaction.atomic():
            written += _write_visits(grouped[KIND_PAGEVIEW] + grouped[KIND_EVENT])
            written += _write_security_events(grouped[KIND_SECURITY])
            written += _write_searches(grouped[KIND_SEARCH])
    except Exception:
        logger.exception('Analytics flush failed; %d record(s) lost', len(records))
        return 0

    return written


def _write_visits(records: list[dict[str, Any]]) -> int:
    """
    Resolve visitors and sessions for a batch, then bulk-insert its rows.

    The whole point of batching is here: N buffered pageviews from M visitors
    cost a bounded number of queries rather than N, regardless of batch size.
    """
    if not records:
        return 0

    for item in records:
        item['_occurred'] = _as_datetime(item.get('occurred_at'))

    visitors = _resolve_visitors(records)
    sessions = _resolve_sessions(records, visitors)

    pageviews: list[PageView] = []
    events: list[Event] = []

    for item in records:
        session = sessions.get(item.get('visitor_id'))
        if session is None:
            continue

        if item['kind'] == KIND_PAGEVIEW:
            pageviews.append(
                PageView(
                    session=session,
                    path=item.get('path', '')[:PageView.PATH_MAX_LENGTH],
                    query_hash=item.get('query_hash', ''),
                    title=(item.get('title') or '')[:PageView.TITLE_MAX_LENGTH],
                    referrer_url=item.get('referrer_url', ''),
                    occurred_at=item['_occurred'],
                    engaged_seconds=item.get('engaged_seconds'),
                    max_scroll_depth=item.get('max_scroll_depth'),
                    status_code=item.get('status_code', 200),
                    response_ms=item.get('response_ms'),
                    is_spa_navigation=item.get('is_spa_navigation', False),
                )
            )
        else:
            events.append(
                Event(
                    session=session,
                    user_id=item.get('user_id'),
                    name=item.get('name', '')[:Event.NAME_MAX_LENGTH],
                    props=item.get('props') or {},
                    value=item.get('value'),
                    occurred_at=item['_occurred'],
                )
            )

    if pageviews:
        PageView.objects.bulk_create(pageviews, batch_size=500)
    if events:
        Event.objects.bulk_create(events, batch_size=500)

    _record_ip_addresses(records)

    return len(pageviews) + len(events)


def _record_ip_addresses(records: list[dict[str, Any]]) -> int:
    """
    Maintain the raw-address listing, if it is switched on.

    Runs in the worker like everything else here, so the request path never
    touches it. Batched deliberately: one address can appear many times in a
    flush, and a ``get_or_create`` per record would turn a 500-row batch into
    1000 queries. Collapsing to distinct addresses first keeps it at four
    regardless of batch size.

    Returns the number of rows written or updated.
    """
    if not get_setting('STORE_RAW_IPS'):
        return 0

    store_private = get_setting('STORE_PRIVATE_IPS')

    # Collapse the batch to one entry per address, keeping the newest sighting
    # and counting how many times it appeared.
    seen: dict[str, dict[str, Any]] = {}
    for item in records:
        address = item.get('ip_address')
        if not address:
            continue

        public = is_public_ip(address)
        if not public and not store_private:
            continue

        entry = seen.get(address)
        if entry is None:
            profile = _profile_for(item)
            seen[address] = {
                'count': 1,
                'occurred': item['_occurred'],
                'is_public': public,
                'path': (item.get('path') or '')[:VisitorIP.PATH_MAX_LENGTH],
                'user_agent': (item.get('user_agent') or '')[:VisitorIP.USER_AGENT_MAX_LENGTH],
                'country': item.get('country_hint', ''),
                'is_bot': profile.is_bot,
            }
            continue

        entry['count'] += 1
        if item['_occurred'] >= entry['occurred']:
            entry['occurred'] = item['_occurred']
            entry['path'] = (item.get('path') or '')[:VisitorIP.PATH_MAX_LENGTH]

    if not seen:
        return 0

    existing = {row.ip_address: row for row in VisitorIP.objects.filter(ip_address__in=seen)}

    to_create = [
        VisitorIP(
            ip_address=address,
            is_public=entry['is_public'],
            visit_count=entry['count'],
            first_seen_at=entry['occurred'],
            last_seen_at=entry['occurred'],
            last_path=entry['path'],
            last_user_agent=entry['user_agent'],
            country=entry['country'],
            is_bot=entry['is_bot'],
        )
        for address, entry in seen.items()
        if address not in existing
    ]
    if to_create:
        VisitorIP.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)

    to_update = []
    for address, row in existing.items():
        entry = seen[address]
        row.visit_count = F('visit_count') + entry['count']
        row.last_seen_at = max(row.last_seen_at, entry['occurred'])
        row.last_path = entry['path']
        row.last_user_agent = entry['user_agent']
        if entry['country']:
            row.country = entry['country']
        row.is_bot = entry['is_bot']
        to_update.append(row)

    if to_update:
        # F() on visit_count so a concurrent flush in another process cannot
        # lose increments to a read-modify-write race — the same guard the
        # previous implementation used.
        VisitorIP.objects.bulk_update(
            to_update,
            ['visit_count', 'last_seen_at', 'last_path', 'last_user_agent',
             'country', 'is_bot'],
            batch_size=500,
        )

    return len(to_create) + len(to_update)


def _resolve_visitors(records: list[dict[str, Any]]) -> dict[str, Visitor]:
    """Fetch or create a Visitor per distinct visitor_id in the batch."""
    seen: dict[str, dict[str, Any]] = {}
    for item in records:
        visitor_id = item.get('visitor_id')
        if visitor_id:
            seen.setdefault(visitor_id, item)

    if not seen:
        return {}

    existing = {v.visitor_id: v for v in Visitor.objects.filter(visitor_id__in=seen)}

    created: list[Visitor] = []
    for visitor_id, item in seen.items():
        if visitor_id in existing:
            continue
        profile = _profile_for(item)
        created.append(
            Visitor(
                visitor_id=visitor_id,
                first_seen_at=item['_occurred'],
                last_seen_at=item['_occurred'],
                is_bot=profile.is_bot,
                user_id=item.get('user_id'),
            )
        )

    if created:
        # ignore_conflicts because another process may have inserted the same
        # visitor_id between the SELECT above and this INSERT. Losing the race
        # is fine; the row exists either way and is re-read below.
        Visitor.objects.bulk_create(created, batch_size=500, ignore_conflicts=True)
        existing = {v.visitor_id: v for v in Visitor.objects.filter(visitor_id__in=seen)}

    _touch_visitors(existing, seen)
    return existing


def _touch_visitors(visitors: dict[str, Visitor], records: dict[str, dict[str, Any]]) -> None:
    """Advance last_seen_at, and attach a user id if one appeared."""
    updates: list[Visitor] = []
    for visitor_id, visitor in visitors.items():
        item = records.get(visitor_id)
        if item is None:
            continue
        changed = False
        if item['_occurred'] > visitor.last_seen_at:
            visitor.last_seen_at = item['_occurred']
            changed = True
        if item.get('user_id') and visitor.user_id != item['user_id']:
            visitor.user_id = item['user_id']
            changed = True
        if changed:
            updates.append(visitor)

    if updates:
        Visitor.objects.bulk_update(updates, ['last_seen_at', 'user'], batch_size=500)


def _resolve_sessions(
    records: list[dict[str, Any]], visitors: dict[str, Visitor]
) -> dict[str, Session]:
    """
    Attach each visitor in the batch to an open session, creating one if needed.

    A session is open if it has no ``ended_at`` and its most recent activity is
    inside the inactivity timeout. That mirrors what the sessionize job uses to
    close them, so the two cannot disagree about where a session boundary is.
    """
    if not visitors:
        return {}

    timeout = timedelta(minutes=get_setting('SESSION_TIMEOUT_MINUTES'))
    earliest = min(item['_occurred'] for item in records)

    open_sessions = {
        session.visitor_id: session
        for session in Session.objects.filter(
            visitor__in=visitors.values(),
            ended_at__isnull=True,
            started_at__gte=earliest - timeout - timedelta(hours=24),
        ).order_by('visitor_id', '-started_at')
    }

    first_record: dict[str, dict[str, Any]] = {}
    for item in records:
        visitor_id = item.get('visitor_id')
        if visitor_id and visitor_id not in first_record:
            first_record[visitor_id] = item

    resolved: dict[str, Session] = {}
    to_create: list[Session] = []
    attributed: list[Visitor] = []

    for visitor_id, visitor in visitors.items():
        item = first_record.get(visitor_id)
        if item is None:
            continue

        candidate = open_sessions.get(visitor.pk)
        if candidate is not None and item['_occurred'] - candidate.started_at < timeout:
            resolved[visitor_id] = candidate
            continue

        to_create.append(_build_session(visitor, item))
        attributed.append(visitor)

    if to_create:
        Session.objects.bulk_create(to_create, batch_size=500)
        for session in to_create:
            resolved[session.visitor.visitor_id] = session
        _save_attribution(attributed)

    return resolved


ATTRIBUTION_FIELDS = (
    'first_touch_channel', 'first_touch_source', 'first_touch_campaign',
    'last_touch_channel', 'last_touch_source', 'last_touch_campaign',
)


def _save_attribution(visitors: list[Visitor]) -> None:
    """
    Persist the attribution fields ``_apply_attribution`` set in memory.

    One bulk_update rather than an UPDATE per visitor: a batch of N new
    visitors was costing N queries here, which is invisible in a small test
    database and the dominant cost in a real flush.
    """
    if visitors:
        Visitor.objects.bulk_update(visitors, list(ATTRIBUTION_FIELDS), batch_size=500)


def _build_session(visitor: Visitor, item: dict[str, Any]) -> Session:
    """Create a fully enriched session from the first record that started it."""
    from . import channels

    profile = _profile_for(item)
    ip_address = item.get('ip_address')
    geo = geo_lookup(ip_address, item.get('country_hint', ''))
    params = item.get('params') or {}
    click_id = channels.extract_click_id(params)

    channel = channels.classify(
        referrer_host=item.get('referrer_host', ''),
        utm_medium=params.get('utm_medium', ''),
        click_id=click_id,
        internal_hosts=_internal_hosts(),
    )

    session = Session(
        visitor=visitor,
        started_at=item['_occurred'],
        landing_path=item.get('path', '')[:Session.PATH_MAX_LENGTH],
        exit_path=item.get('path', '')[:Session.PATH_MAX_LENGTH],
        referrer_host=item.get('referrer_host', ''),
        referrer_url=item.get('referrer_url', ''),
        channel=channel,
        utm_source=params.get('utm_source', '')[:Session.UTM_MAX_LENGTH],
        utm_medium=params.get('utm_medium', '')[:Session.UTM_MAX_LENGTH],
        utm_campaign=params.get('utm_campaign', '')[:Session.UTM_MAX_LENGTH],
        utm_term=params.get('utm_term', '')[:Session.UTM_MAX_LENGTH],
        utm_content=params.get('utm_content', '')[:Session.UTM_MAX_LENGTH],
        click_id=click_id,
        ip_hash=item.get('ip_hash', ''),
        ip_truncated=truncate_ip(ip_address),
        language=item.get('language', '')[:35],
        browser=profile.browser,
        browser_version=profile.browser_version,
        os=profile.os,
        os_version=profile.os_version,
        device_type=profile.device_type,
        is_bot=profile.is_bot or geo.is_datacenter,
        bot_reason=profile.bot_reason or ('datacenter asn' if geo.is_datacenter else ''),
        **geo.as_session_fields(),
    )
    _apply_attribution(visitor, session)
    return session


def _apply_attribution(visitor: Visitor, session: Session) -> None:
    """
    Record first-touch once and last-touch every time.

    They answer different questions — which channel found this person, and
    which one brought them back — so overwriting first-touch would destroy the
    only copy of the first answer.

    Mutates the visitor in memory only. ``_save_attribution`` writes the whole
    batch in one query afterwards — doing the UPDATE here cost one query per
    new visitor in a flush.
    """
    source = session.utm_source or session.referrer_host

    if not visitor.first_touch_channel:
        visitor.first_touch_channel = session.channel
        visitor.first_touch_source = source
        visitor.first_touch_campaign = session.utm_campaign

    visitor.last_touch_channel = session.channel
    visitor.last_touch_source = source
    visitor.last_touch_campaign = session.utm_campaign


def _write_security_events(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    SecurityEvent.objects.bulk_create(
        [
            SecurityEvent(
                kind=item.get('event_kind', ''),
                ip_hash=item.get('ip_hash', ''),
                ip_truncated=item.get('ip_truncated'),
                asn=item.get('asn', ''),
                country=item.get('country', ''),
                path=item.get('path', ''),
                username_attempted=item.get('username_attempted', ''),
                occurred_at=_as_datetime(item.get('occurred_at')),
                metadata=item.get('metadata') or {},
            )
            for item in records
        ],
        batch_size=500,
    )
    return len(records)


def _write_searches(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    SearchQuery.objects.bulk_create(
        [
            SearchQuery(
                session_id=item.get('session_id'),
                query=item.get('query', '')[:SearchQuery.QUERY_MAX_LENGTH],
                normalized_query=normalize_search(item.get('query', '')),
                result_count=item.get('result_count', 0),
                clicked_result=item.get('clicked_result', False),
                occurred_at=_as_datetime(item.get('occurred_at')),
            )
            for item in records
        ],
        batch_size=500,
    )
    return len(records)


def normalize_search(query: str) -> str:
    """Lowercase and collapse whitespace so the report groups equivalent queries."""
    return ' '.join((query or '').lower().split())[:SearchQuery.QUERY_MAX_LENGTH]


# ---------------------------------------------------------------------------
# Sessionization
# ---------------------------------------------------------------------------

def sessionize(now: datetime | None = None) -> int:
    """
    Close sessions idle for longer than the timeout. Returns the number closed.

    Idempotent: a session already carrying an ``ended_at`` is excluded by the
    filter, so re-running changes nothing.
    """
    now = now or django_timezone.now()
    cutoff = now - timedelta(minutes=get_setting('SESSION_TIMEOUT_MINUTES'))

    stale = (
        Session.objects.filter(ended_at__isnull=True)
        .annotate(last_activity=Max('pageviews__occurred_at'))
        .filter(Q(last_activity__lt=cutoff) | Q(last_activity__isnull=True, started_at__lt=cutoff))
    )

    closed = 0
    for session in stale.iterator(chunk_size=500):
        _close_session(session)
        closed += 1

    if closed:
        logger.info('Closed %d idle analytics session(s)', closed)
    return closed


def _close_session(session: Session) -> None:
    """Compute a session's summary fields from its pageviews and stamp it closed."""
    stats = session.pageviews.aggregate(
        count=Count('id'),
        first=Min('occurred_at'),
        last=Max('occurred_at'),
        engaged=Sum('engaged_seconds'),
    )
    count = stats['count'] or 0
    last = stats['last'] or session.started_at

    exit_view = session.pageviews.order_by('-occurred_at').first()

    # Engaged time is the honest duration: a tab left open for an hour is not
    # an hour of attention. Wall clock is the fallback only when the beacon
    # reported nothing, which happens when Tier 2 is off or consent is absent.
    engaged = stats['engaged'] or 0
    wall_clock = int((last - session.started_at).total_seconds())

    session.ended_at = last
    session.pageview_count = count
    session.duration_seconds = engaged or max(wall_clock, 0)
    session.is_bounce = count <= 1 and engaged < 10
    if exit_view is not None:
        session.exit_path = exit_view.path[:Session.PATH_MAX_LENGTH]

    session.save(
        update_fields=[
            'ended_at', 'pageview_count', 'duration_seconds', 'is_bounce', 'exit_path'
        ]
    )


# ---------------------------------------------------------------------------
# Rollup
# ---------------------------------------------------------------------------

def rollup(target_date: date) -> int:
    """
    Rebuild ``DailyStat`` for one day. Returns the number of rows written.

    Idempotent by construction: the day's rows are deleted and rewritten inside
    one transaction, so re-running for any date is always safe and always
    produces the same result.

    Postgres treats every NULL as distinct, which means the unique constraint
    cannot prevent duplicate site-wide rows on its own. Delete-then-write is
    what actually guarantees uniqueness here.
    """
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    views = (
        PageView.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        .exclude(session__is_bot=True)
        .select_related('session')
    )

    # Dimension tuple -> accumulator. Aggregated in Python rather than with
    # five GROUP BY queries because a day's rows are read once either way, and
    # unique-visitor counting needs set semantics the database would have to
    # do with COUNT(DISTINCT) per combination.
    buckets: dict[tuple, dict[str, Any]] = {}

    for view in views.iterator(chunk_size=2_000):
        session = view.session
        dimensions = (
            view.path,
            session.country or '',
            session.device_type or '',
            session.channel or '',
        )
        for combination in _dimension_combinations(dimensions):
            bucket = buckets.setdefault(
                combination,
                {'pageviews': 0, 'visitors': set(), 'sessions': set(), 'engaged': 0},
            )
            bucket['pageviews'] += 1
            bucket['visitors'].add(session.visitor_id)
            bucket['sessions'].add(session.pk)
            bucket['engaged'] += view.engaged_seconds or 0

    bounces = _bounce_counts(start, end)

    rows = [
        DailyStat(
            date=target_date,
            path=combination[0],
            country=combination[1],
            device_type=combination[2],
            channel=combination[3],
            pageviews=bucket['pageviews'],
            unique_visitors=len(bucket['visitors']),
            sessions=len(bucket['sessions']),
            bounces=bounces.get(combination, 0),
            total_engaged_seconds=bucket['engaged'],
        )
        for combination, bucket in buckets.items()
    ]

    with transaction.atomic():
        DailyStat.objects.filter(date=target_date).delete()
        if rows:
            DailyStat.objects.bulk_create(rows, batch_size=500)

    logger.info('Rolled up %s: %d DailyStat row(s)', target_date, len(rows))
    return len(rows)


def _dimension_combinations(dimensions: tuple) -> Iterable[tuple]:
    """
    Yield the dimension tuples one pageview contributes to.

    A null dimension means "all", so a single view increments the fully
    detailed row, the site-wide total, and each single-dimension breakdown.
    The full power set would be 16 rows per view; these five are the ones the
    dashboard actually reads, and generating the rest would multiply the table
    for reports nobody runs.
    """
    path, country, device, channel = dimensions
    yield (path, country, device, channel)
    yield (None, None, None, None)
    yield (path, None, None, None)
    yield (None, country, None, None)
    yield (None, None, device, None)
    yield (None, None, None, channel)


def _bounce_counts(start: datetime, end: datetime) -> dict[tuple, int]:
    """Count bounced sessions per dimension combination for the day."""
    counts: dict[tuple, int] = defaultdict(int)
    bounced = Session.objects.filter(
        started_at__gte=start, started_at__lt=end, is_bounce=True, is_bot=False
    ).only('landing_path', 'country', 'device_type', 'channel')

    for session in bounced.iterator(chunk_size=2_000):
        dimensions = (
            session.landing_path,
            session.country or '',
            session.device_type or '',
            session.channel or '',
        )
        for combination in _dimension_combinations(dimensions):
            counts[combination] += 1
    return dict(counts)


def rebuild_stats(start_date: date, end_date: date) -> int:
    """Re-run the rollup across a date range. Returns total rows written."""
    total = 0
    current = start_date
    while current <= end_date:
        total += rollup(current)
        current += timedelta(days=1)
    return total


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def enforce_retention(now: datetime | None = None) -> dict[str, int]:
    """
    Delete expired raw rows and blank expired location data.

    Rollups are never touched: ``DailyStat`` is the long-term record and is
    kept indefinitely. Deletion runs in batches so a large backlog cannot hold
    a long transaction open against the production database.
    """
    now = now or django_timezone.now()
    raw_cutoff = now - timedelta(days=get_setting('RAW_RETENTION_DAYS'))
    location_cutoff = now - timedelta(days=get_setting('LOCATION_RETENTION_DAYS'))
    batch = get_setting('PURGE_BATCH_SIZE')

    deleted = {
        'pageviews': _delete_in_batches(PageView.objects.filter(occurred_at__lt=raw_cutoff), batch),
        'events': _delete_in_batches(Event.objects.filter(occurred_at__lt=raw_cutoff), batch),
        'security_events': _delete_in_batches(
            SecurityEvent.objects.filter(occurred_at__lt=raw_cutoff), batch
        ),
        'searches': _delete_in_batches(
            SearchQuery.objects.filter(occurred_at__lt=raw_cutoff), batch
        ),
    }

    # Sessions outlive their pageviews because the rollup is derived from them,
    # but the location data inside them expires sooner and separately.
    deleted['locations_cleared'] = Session.objects.filter(
        started_at__lt=location_cutoff
    ).exclude(ip_truncated__isnull=True, latitude__isnull=True).update(
        ip_truncated=None, latitude=None, longitude=None, city='', region=''
    )

    deleted['sessions'] = _delete_in_batches(
        Session.objects.filter(started_at__lt=raw_cutoff, pageviews__isnull=True), batch
    )

    # Raw addresses age out on their own clock. Deleted rather than blanked:
    # a VisitorIP row with its address removed holds nothing worth keeping.
    ip_cutoff = now - timedelta(days=get_setting('IP_RETENTION_DAYS'))
    deleted['ip_addresses'] = _delete_in_batches(
        VisitorIP.objects.filter(last_seen_at__lt=ip_cutoff), batch
    )

    logger.info('Retention pass complete: %s', deleted)
    return deleted


def _delete_in_batches(queryset, batch_size: int) -> int:
    """Delete a queryset in bounded chunks, returning the total removed."""
    total = 0
    while True:
        ids = list(queryset.values_list('pk', flat=True)[:batch_size])
        if not ids:
            return total
        removed, _ = queryset.model.objects.filter(pk__in=ids).delete()
        total += removed
        if len(ids) < batch_size:
            return total


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """
    Start the background thread, unless it is already running or disabled.

    Called from ``AppConfig.ready()``, which Django may invoke more than once
    (the autoreloader runs it in both processes), so this must be idempotent.
    """
    global _scheduler_thread

    if not get_setting('ENABLED') or not get_setting('RUN_INLINE_SCHEDULER'):
        return
    if _is_management_command_that_should_not_schedule():
        return

    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name='analytics-pipeline',
            daemon=True,
        )
        _scheduler_thread.start()
        logger.info('Analytics pipeline thread started')


def _is_management_command_that_should_not_schedule() -> bool:
    """
    True while running a command that must not spawn a background writer.

    Migrations and test runs in particular: a thread writing to the database
    during ``migrate`` races the schema change, and during tests it writes into
    whichever transaction the test case is about to roll back.
    """
    import sys

    if len(sys.argv) < 2:
        return False
    blocked = {
        'migrate', 'makemigrations', 'test', 'collectstatic', 'shell',
        'dbshell', 'showmigrations', 'sqlmigrate', 'flush', 'loaddata',
        'dumpdata', 'createsuperuser', 'check',
    }
    return sys.argv[1] in blocked


def _initial_next_run() -> dict[str, float]:
    """
    Make every periodic job due on the first tick after startup.

    These were previously seeded one full interval ahead, which meant a job
    only ever ran if the process outlived its own interval. The rollup's
    interval is an hour, so under the dev server's autoreloader — or any
    platform that recycles the instance — it never ran at all: raw rows kept
    accumulating while ``DailyStat`` stayed empty, and the admin dashboard,
    which reads only rollups, showed nothing. Retention failed the same way
    against its 24-hour interval, leaving the privacy window unenforced.

    Every job is idempotent and cheap when there is nothing to do, so running
    each once per boot costs a few queries and removes the dependency on
    uptime.
    """
    now = time.monotonic()
    return {'sessionize': now, 'rollup': now, 'retention': now}


def _run_due_jobs(next_run: dict[str, float], now: float) -> None:
    """Run each periodic job whose turn has come, and reschedule it."""
    if now >= next_run['sessionize']:
        next_run['sessionize'] = now + get_setting('SESSIONIZE_INTERVAL_SECONDS')
        _run_locked('sessionize', sessionize)
    if now >= next_run['rollup']:
        next_run['rollup'] = now + get_setting('ROLLUP_INTERVAL_SECONDS')
        _run_locked('rollup', rollup_recent)
    if now >= next_run['retention']:
        next_run['retention'] = now + get_setting('RETENTION_INTERVAL_SECONDS')
        _run_locked('retention', enforce_retention)
        # Only acts once PageView has actually been converted, which is a
        # deliberate manual step. Runs on the retention tick so a month
        # boundary can never arrive without a partition ready.
        _run_locked('partitions', _ensure_partitions)


def _scheduler_loop() -> None:
    """Run the periodic jobs forever, at their configured intervals."""
    next_run = _initial_next_run()
    interval = get_setting('FLUSH_INTERVAL_SECONDS')

    while True:
        try:
            time.sleep(interval)
            _run_safely('flush', flush)
            _run_due_jobs(next_run, time.monotonic())
        except Exception:
            # The loop must outlive any single failure, or one bad batch stops
            # collection until the next deploy.
            logger.exception('Analytics scheduler iteration failed')


def _ensure_partitions() -> list[str]:
    """Create upcoming monthly partitions, if the table is partitioned at all."""
    from .partitioning import ensure_partitions

    return ensure_partitions()


def rollup_recent() -> int:
    """
    Roll up today and yesterday.

    Today because the dashboard should not be a day stale; yesterday because
    late-arriving beacon data (a tab hidden across midnight) changes it after
    the day has ended.
    """
    today = django_timezone.now().date()
    return rebuild_stats(today - timedelta(days=1), today)


def _run_safely(name: str, job) -> None:
    try:
        job()
    except Exception:
        logger.exception('Analytics job %r failed', name)


def _run_locked(name: str, job) -> None:
    """Run a job only if this process can take the advisory lock."""
    if not _acquire_advisory_lock():
        logger.debug('Analytics job %r skipped: lock held elsewhere', name)
        return
    try:
        _run_safely(name, job)
    finally:
        _release_advisory_lock()


def _acquire_advisory_lock() -> bool:
    """
    Take the cross-process job lock. Always True on backends without one.

    SQLite has no advisory locks and no second process to contend with in the
    configurations this project uses, so the lock degrades to a no-op rather
    than blocking local development.
    """
    if connection.vendor != 'postgresql':
        return True
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK_KEY])
        return bool(cursor.fetchone()[0])


def _release_advisory_lock() -> None:
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK_KEY])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_for(item: dict[str, Any]):
    """Parse the client profile once per record, caching it on the record."""
    cached = item.get('_profile')
    if cached is None:
        cached = parse_user_agent(item.get('user_agent', ''), item.get('client_hints'))
        item['_profile'] = cached
    return cached


def _as_datetime(value: Any) -> datetime:
    """Accept a POSIX timestamp or a datetime and return an aware datetime."""
    if isinstance(value, datetime):
        return value if django_timezone.is_aware(value) else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return django_timezone.now()


def _internal_hosts() -> frozenset[str]:
    """This site's own hostnames, so self-referrals are classed as internal."""
    from django.conf import settings

    return frozenset(
        host.lower().lstrip('.') for host in settings.ALLOWED_HOSTS if host not in ('*',)
    )
