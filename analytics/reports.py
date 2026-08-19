"""
The queries behind the admin dashboard.

The rule that makes the dashboard fast: **time series and breakdowns read
``DailyStat``, never the raw tables.** A rollup row already holds the counts, so
a 30-day chart is 30 indexed rows regardless of whether the period contained a
thousand pageviews or ten million.

Three things legitimately cannot come from the rollup and are documented where
they appear: the live counter (by definition about rows too recent to have been
rolled up), Core Web Vitals percentiles (a percentile is not additive, so it
cannot be pre-aggregated into a daily row and then combined), and the security
and search reports (which are lists of individual rows, not counts).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from .defaults import get_setting
from .models import DailyStat, Event, PageView, SearchQuery, SecurityEvent, Session

# Rows where every dimension is null are the site-wide totals for the day.
SITE_WIDE = {
    'path__isnull': True,
    'country__isnull': True,
    'device_type__isnull': True,
    'channel__isnull': True,
}


def as_datetime_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """
    Convert an inclusive date range into half-open datetime bounds.

    Queries against the raw tables must filter on the bare timestamp column.
    Using ``occurred_at__date__gte`` instead wraps the column in a function,
    which makes both the BRIN and the B-tree indexes unusable and forces a full
    scan — measured at 200ms+ per query on a million rows, versus single digits
    with these bounds.
    """
    current_tz = timezone.get_current_timezone()
    start_at = datetime.combine(start, time.min, tzinfo=current_tz)
    end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=current_tz)
    return start_at, end_at


def date_range(days: int | None = None) -> tuple[date, date]:
    """Return the inclusive (start, end) window the dashboard defaults to."""
    days = days or get_setting('DASHBOARD_DEFAULT_DAYS')
    end = timezone.now().date()
    return end - timedelta(days=days - 1), end


def summary(start: date, end: date) -> dict[str, Any]:
    """Headline totals for the period, from the site-wide rollup rows."""
    totals = DailyStat.objects.filter(date__gte=start, date__lte=end, **SITE_WIDE).aggregate(
        pageviews=Sum('pageviews'),
        sessions=Sum('sessions'),
        bounces=Sum('bounces'),
        engaged=Sum('total_engaged_seconds'),
        visitors=Sum('unique_visitors'),
    )

    sessions = totals['sessions'] or 0
    pageviews = totals['pageviews'] or 0
    engaged = totals['engaged'] or 0

    return {
        'pageviews': pageviews,
        # Summed across days, so a person visiting on three days counts three
        # times. That is what a daily-rotating identifier can honestly report;
        # calling it "unique visitors" over a month would be a lie.
        'visitor_days': totals['visitors'] or 0,
        'sessions': sessions,
        'bounces': totals['bounces'] or 0,
        'bounce_rate': round((totals['bounces'] or 0) / sessions * 100, 1) if sessions else 0.0,
        'engaged_seconds': engaged,
        'avg_engaged_seconds': round(engaged / sessions) if sessions else 0,
        'pages_per_session': round(pageviews / sessions, 2) if sessions else 0.0,
    }


def time_series(start: date, end: date) -> list[dict[str, Any]]:
    """
    Daily pageviews, visitors and sessions across the period.

    Days with no traffic have no rollup row, so the range is filled in here —
    a chart with gaps would misrepresent a quiet day as missing data.
    """
    rows = {
        row['date']: row
        for row in DailyStat.objects.filter(
            date__gte=start, date__lte=end, **SITE_WIDE
        ).values('date', 'pageviews', 'unique_visitors', 'sessions')
    }

    series = []
    current = start
    while current <= end:
        row = rows.get(current)
        series.append({
            'date': current.isoformat(),
            'pageviews': row['pageviews'] if row else 0,
            'visitors': row['unique_visitors'] if row else 0,
            'sessions': row['sessions'] if row else 0,
        })
        current += timedelta(days=1)
    return series


def breakdown(start: date, end: date, dimension: str, limit: int | None = None) -> list[dict]:
    """
    Top values for one dimension, from the single-dimension rollup rows.

    Selects rows where the requested dimension is set and every other one is
    null, which is exactly the shape the rollup writes for a breakdown.
    """
    limit = limit or get_setting('DASHBOARD_TOP_N')
    filters = {f'{name}__isnull': True for name in ('path', 'country', 'device_type', 'channel')}
    filters.pop(f'{dimension}__isnull')
    filters[f'{dimension}__isnull'] = False

    return list(
        DailyStat.objects.filter(date__gte=start, date__lte=end, **filters)
        .values(value=F(dimension))
        .annotate(
            pageviews=Sum('pageviews'),
            visitors=Sum('unique_visitors'),
            sessions=Sum('sessions'),
            engaged=Sum('total_engaged_seconds'),
        )
        .order_by('-pageviews')[:limit]
    )


def top_referrers(start: date, end: date, limit: int | None = None) -> list[dict]:
    """
    Referring hosts for the period.

    Read from ``Session`` rather than ``DailyStat``: referrer host is not a
    rollup dimension, because its cardinality is unbounded and adding it would
    multiply the rollup table by the number of distinct referrers. Sessions are
    a far smaller table than pageviews, so this stays cheap.
    """
    limit = limit or get_setting('DASHBOARD_TOP_N')
    start_at, end_at = as_datetime_bounds(start, end)
    return list(
        Session.objects.filter(
            started_at__gte=start_at, started_at__lt=end_at, is_bot=False
        )
        .exclude(referrer_host='')
        .values('referrer_host')
        .annotate(sessions=Count('id'))
        .order_by('-sessions')[:limit]
    )


def live_visitor_count() -> int:
    """
    Visitors active in the last few minutes.

    Necessarily reads the raw table: these rows are minutes old and the rollup
    runs hourly. Bounded by the time filter, which the BRIN index on
    ``occurred_at`` serves.
    """
    since = timezone.now() - timedelta(minutes=get_setting('LIVE_WINDOW_MINUTES'))
    return (
        PageView.objects.filter(occurred_at__gte=since)
        .exclude(session__is_bot=True)
        .values('session__visitor_id')
        .distinct()
        .count()
    )


def web_vitals_p75(start: date, end: date, limit: int | None = None) -> list[dict]:
    """
    75th-percentile Core Web Vitals per page.

    Cannot come from ``DailyStat``: a percentile is not additive, so daily p75
    values cannot be combined into a period p75. Computed in Python over the
    period's ``web_vital`` events, which is a small enough set at this site's
    volume — and the ``(name, occurred_at)`` index keeps the scan bounded.
    """
    limit = limit or get_setting('DASHBOARD_TOP_N')
    start_at, end_at = as_datetime_bounds(start, end)
    events = (
        Event.objects.filter(
            name='web_vital',
            occurred_at__gte=start_at,
            occurred_at__lt=end_at,
            value__isnull=False,
        )
        .values_list('props', 'value')
    )

    grouped: dict[str, list[float]] = {}
    for props, value in events.iterator(chunk_size=2_000):
        metric = (props or {}).get('metric')
        if metric:
            grouped.setdefault(metric, []).append(float(value))

    return sorted(
        (
            {
                'metric': metric,
                'p75': _percentile(values, 75),
                'samples': len(values),
            }
            for metric, values in grouped.items()
        ),
        key=lambda row: row['metric'],
    )[:limit]


def zero_result_searches(start: date, end: date, limit: int | None = None) -> list[dict]:
    """
    Searches that returned nothing, most frequent first.

    The most actionable report here: a list, in visitors' own words, of what
    they expected to find and did not. Empty until the site has a search box.
    """
    limit = limit or get_setting('DASHBOARD_TOP_N')
    start_at, end_at = as_datetime_bounds(start, end)
    return list(
        SearchQuery.objects.filter(
            occurred_at__gte=start_at, occurred_at__lt=end_at, result_count=0
        )
        .values('normalized_query')
        .annotate(searches=Count('id'))
        .order_by('-searches')[:limit]
    )


def recent_security_events(limit: int = 20) -> list[SecurityEvent]:
    """The newest abuse signals, for the dashboard panel."""
    return list(SecurityEvent.objects.order_by('-occurred_at')[:limit])


def security_summary(start: date, end: date) -> list[dict]:
    """Counts per security event kind for the period."""
    start_at, end_at = as_datetime_bounds(start, end)
    return list(
        SecurityEvent.objects.filter(
            occurred_at__gte=start_at, occurred_at__lt=end_at
        )
        .values('kind')
        .annotate(count=Count('id'))
        .order_by('-count')
    )


def not_found_paths(start: date, end: date, limit: int | None = None) -> list[dict]:
    """404s with their referrers, which is what makes broken inbound links findable."""
    limit = limit or get_setting('DASHBOARD_TOP_N')
    start_at, end_at = as_datetime_bounds(start, end)
    return list(
        PageView.objects.filter(
            status_code=404, occurred_at__gte=start_at, occurred_at__lt=end_at
        )
        .values('path', 'referrer_url')
        .annotate(hits=Count('id'))
        .order_by('-hits')[:limit]
    )


def bot_split(start: date, end: date) -> dict[str, int]:
    """Human versus bot sessions, from the session table's own flag."""
    start_at, end_at = as_datetime_bounds(start, end)
    counts = Session.objects.filter(
        started_at__gte=start_at, started_at__lt=end_at
    ).aggregate(
        humans=Count('id', filter=Q(is_bot=False)),
        bots=Count('id', filter=Q(is_bot=True)),
    )
    return {'humans': counts['humans'] or 0, 'bots': counts['bots'] or 0}


def _percentile(values: list[float], percentile: int) -> float:
    """
    Nearest-rank percentile.

    Deliberately not interpolated: web vitals are reported as whole
    milliseconds and an interpolated value would imply precision the
    measurement does not have.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(percentile / 100 * len(ordered)) - 1))
    return round(ordered[index], 3)
