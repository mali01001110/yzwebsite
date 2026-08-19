"""
Read-only admin for the collected data, plus the dashboard.

Everything here is observed, never entered, so nothing is addable or editable —
a hand-edited pageview would misrepresent the traffic record, which is the only
thing this data is for. Deletion stays available to superusers because an
erasure request has to be answerable.

The dashboard is mounted inside the admin via ``get_urls()`` on the
``DailyStat`` model admin, so it inherits the admin's authentication, styling
and navigation instead of reimplementing any of them.

Follows the conventions already in ``api/admin.py``: ``@admin.register``,
``list_display`` tuples, ``@admin.display`` for computed columns, truncated
previews, and a docstring on each class explaining why it is shaped that way.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal

from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import Truncator

from . import reports
from .defaults import get_setting
from .models import (
    DailyStat,
    Event,
    ExperimentAssignment,
    PageView,
    SearchQuery,
    SecurityEvent,
    Session,
    Visitor,
    VisitorIP,
)
from .paginators import EstimatedCountPaginator

PATH_PREVIEW_LENGTH = 60
PROPS_PREVIEW_LENGTH = 70
USER_AGENT_PREVIEW_LENGTH = 60
CSV_EXPORT_LIMIT = 50_000


class ReadOnlyAdmin(admin.ModelAdmin):
    """
    Base for every model here: observable, deletable by a superuser, never edited.

    ``show_full_result_count`` is off because the admin's "show all" link runs a
    second unfiltered COUNT(*) that the estimating paginator was added to avoid.
    """

    paginator = EstimatedCountPaginator
    show_full_result_count = False
    actions = ('export_as_csv',)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Erasure requests have to be answerable, but only by the site owner."""
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    @admin.action(description='Export selected rows to CSV')
    def export_as_csv(self, request, queryset) -> HttpResponse:
        """
        Stream the selection as CSV.

        Capped, because the admin's "select all" spans the whole table and an
        uncapped export of an append-only log would build the entire thing in
        memory before sending a byte.
        """
        field_names = [field.name for field in self.model._meta.fields]
        model_name = self.model._meta.model_name

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{model_name}.csv"'

        writer = csv.writer(response)
        writer.writerow(field_names)
        for row in queryset[:CSV_EXPORT_LIMIT].iterator(chunk_size=2_000):
            writer.writerow([getattr(row, name) for name in field_names])
        return response


class SessionInline(admin.TabularInline):
    """A visitor's sessions, newest first, on the visitor change page."""

    model = Session
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('started_at', 'ended_at', 'channel', 'country', 'device_type',
              'pageview_count', 'duration_seconds', 'is_bounce')
    readonly_fields = fields
    ordering = ('-started_at',)

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class PageViewInline(admin.TabularInline):
    """A session's pageview timeline on the session change page."""

    model = PageView
    extra = 0
    can_delete = False
    fields = ('occurred_at', 'path', 'title', 'engaged_seconds', 'max_scroll_depth',
              'status_code', 'response_ms')
    readonly_fields = fields
    ordering = ('occurred_at',)

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Visitor)
class VisitorAdmin(ReadOnlyAdmin):
    """
    One row per visitor per rotation window.

    The identifier is a rotating salted hash, so this list is a record of
    distinct daily visits and deliberately cannot be joined across days.
    """

    list_display = ('short_id', 'first_seen_at', 'last_seen_at', 'session_count',
                    'first_touch_channel', 'last_touch_channel', 'is_bot', 'user')
    list_filter = ('is_bot', 'first_touch_channel', 'last_touch_channel', 'last_seen_at')
    search_fields = ('visitor_id',)
    date_hierarchy = 'last_seen_at'
    ordering = ('-last_seen_at',)
    inlines = (SessionInline,)

    def get_queryset(self, request):
        # select_related on the user and a session count annotation, so the
        # changelist stays two queries regardless of page size.
        from django.db.models import Count

        return (
            super().get_queryset(request)
            .select_related('user')
            .annotate(_session_count=Count('sessions'))
        )

    @admin.display(description='Visitor', ordering='visitor_id')
    def short_id(self, visitor: Visitor) -> str:
        return visitor.visitor_id[:16]

    @admin.display(description='Sessions', ordering='_session_count')
    def session_count(self, visitor: Visitor) -> int:
        return visitor._session_count


@admin.register(Session)
class SessionAdmin(ReadOnlyAdmin):
    """One visit. The pageview timeline is inlined below each row."""

    list_display = ('started_at', 'short_visitor', 'channel', 'country', 'device_type',
                    'browser', 'pageview_count', 'duration_seconds', 'is_bounce', 'is_bot')
    list_filter = ('is_bot', 'channel', 'device_type', 'is_datacenter', 'country', 'started_at')
    search_fields = ('visitor__visitor_id', 'referrer_host', 'utm_campaign', 'ip_hash')
    date_hierarchy = 'started_at'
    ordering = ('-started_at',)
    inlines = (PageViewInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('visitor')

    @admin.display(description='Visitor', ordering='visitor__visitor_id')
    def short_visitor(self, session: Session) -> str:
        return session.visitor.visitor_id[:16]


@admin.register(PageView)
class PageViewAdmin(ReadOnlyAdmin):
    """The raw append-only pageview log."""

    list_display = ('occurred_at', 'path_preview', 'status_code', 'engaged_seconds',
                    'max_scroll_depth', 'response_ms', 'is_spa_navigation')
    list_filter = ('status_code', 'is_spa_navigation', 'occurred_at')
    search_fields = ('path', 'title')
    date_hierarchy = 'occurred_at'
    ordering = ('-occurred_at',)

    def get_queryset(self, request):
        # only() rather than select_related: the changelist renders no session
        # field, so fetching the join would be work for nothing.
        return super().get_queryset(request).only(
            'occurred_at', 'path', 'status_code', 'engaged_seconds',
            'max_scroll_depth', 'response_ms', 'is_spa_navigation',
        )

    @admin.display(description='Path', ordering='path')
    def path_preview(self, view: PageView) -> str:
        return Truncator(view.path).chars(PATH_PREVIEW_LENGTH)


@admin.register(Event)
class EventAdmin(ReadOnlyAdmin):
    """Named events with their scrubbed properties."""

    list_display = ('occurred_at', 'name', 'props_preview', 'value', 'user')
    list_filter = ('name', 'occurred_at')
    search_fields = ('name',)
    date_hierarchy = 'occurred_at'
    ordering = ('-occurred_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    @admin.display(description='Properties')
    def props_preview(self, event: Event) -> str:
        return Truncator(str(event.props)).chars(PROPS_PREVIEW_LENGTH)


@admin.register(SecurityEvent)
class SecurityEventAdmin(ReadOnlyAdmin):
    """Abuse signals. Recorded only — this app never blocks anything."""

    list_display = ('occurred_at', 'kind', 'ip_truncated', 'country', 'path_preview',
                    'username_attempted')
    list_filter = ('kind', 'country', 'occurred_at')
    search_fields = ('ip_hash', 'path', 'username_attempted')
    date_hierarchy = 'occurred_at'
    ordering = ('-occurred_at',)

    @admin.display(description='Path', ordering='path')
    def path_preview(self, event: SecurityEvent) -> str:
        return Truncator(event.path).chars(PATH_PREVIEW_LENGTH)


@admin.register(SearchQuery)
class SearchQueryAdmin(ReadOnlyAdmin):
    """
    Internal site searches.

    Empty until the site has a search box; the zero-result report on the
    dashboard is built and waiting for it.
    """

    list_display = ('occurred_at', 'query', 'result_count', 'clicked_result')
    list_filter = ('clicked_result', 'result_count', 'occurred_at')
    search_fields = ('query', 'normalized_query')
    date_hierarchy = 'occurred_at'
    ordering = ('-occurred_at',)


@admin.register(ExperimentAssignment)
class ExperimentAssignmentAdmin(ReadOnlyAdmin):
    """Which variant each visitor was assigned, for auditing the split."""

    list_display = ('experiment_key', 'variant', 'short_visitor', 'assigned_at')
    list_filter = ('experiment_key', 'variant', 'assigned_at')
    search_fields = ('experiment_key', 'visitor__visitor_id')
    date_hierarchy = 'assigned_at'
    ordering = ('-assigned_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('visitor')

    @admin.display(description='Visitor')
    def short_visitor(self, assignment: ExperimentAssignment) -> str:
        return assignment.visitor.visitor_id[:16]


@admin.register(VisitorIP)
class VisitorIPAdmin(ReadOnlyAdmin):
    """
    The IP address listing — one row per address that has loaded the site.

    Read-only for the same reason its predecessor was: a hand-edited address
    would misrepresent the traffic record. Deletion stays available to
    superusers because an address is personal data and may have to be erased on
    request.

    Defaults to showing public addresses only. Loopback and private-range rows
    are recorded (so local development shows something) but they say nothing
    about where a visitor came from, so they are filtered out of the default
    view rather than cluttering it.
    """

    list_display = ('ip_address', 'is_public', 'visit_count', 'country',
                    'last_seen_at', 'first_seen_at', 'last_path',
                    'user_agent_preview', 'is_bot')
    list_filter = ('is_public', 'is_bot', 'country', 'last_seen_at')
    search_fields = ('ip_address', 'last_path', 'last_user_agent', 'country')
    date_hierarchy = 'last_seen_at'
    ordering = ('-last_seen_at',)

    def get_queryset(self, request):
        """
        Show public addresses unless the viewer asks otherwise.

        Applied only when `is_public` is not already among the active filters,
        so choosing "No" in the sidebar still works.
        """
        queryset = super().get_queryset(request)
        if 'is_public__exact' in request.GET:
            return queryset
        return queryset.filter(is_public=True)

    @admin.display(description='User agent')
    def user_agent_preview(self, visitor_ip: VisitorIP) -> str:
        return Truncator(visitor_ip.last_user_agent).chars(USER_AGENT_PREVIEW_LENGTH)


@admin.register(DailyStat)
class DailyStatAdmin(ReadOnlyAdmin):
    """
    The pre-aggregated rollup, and the host for the dashboard view.

    The dashboard hangs off this model admin because everything it charts comes
    from this table, so "Daily stats → Dashboard" is where somebody looking for
    it would actually go.
    """

    list_display = ('date', 'scope', 'pageviews', 'unique_visitors', 'sessions',
                    'bounces', 'total_engaged_seconds')
    list_filter = ('date', 'country', 'device_type', 'channel')
    search_fields = ('path',)
    date_hierarchy = 'date'
    ordering = ('-date',)

    def get_urls(self):
        # Prepended, not appended: Django resolves in order and the admin's
        # catch-all <path:object_id> route would otherwise swallow 'dashboard'.
        return [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.dashboard_view),
                name='analytics_dashboard',
            ),
            path(
                'dashboard/data/',
                self.admin_site.admin_view(self.dashboard_data_view),
                name='analytics_dashboard_data',
            ),
        ] + super().get_urls()

    @admin.display(description='Scope')
    def scope(self, row: DailyStat) -> str:
        parts = [p for p in (row.path, row.country, row.device_type, row.channel) if p]
        return ' · '.join(parts) if parts else format_html('<em>site-wide</em>')

    def dashboard_view(self, request):
        """Render the dashboard shell. Data arrives from the JSON view below."""
        days = _requested_days(request)
        start, end = reports.date_range(days)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Visitor analytics',
            'days': days,
            'start': start,
            'end': end,
            'summary': reports.summary(start, end),
            'live_count': reports.live_visitor_count(),
            'live_window': get_setting('LIVE_WINDOW_MINUTES'),
            'data_url': reverse('admin:analytics_dashboard_data'),
            'range_options': (7, 30, 90, 365),
        }
        return render(request, 'admin/analytics/dashboard.html', context)

    def dashboard_data_view(self, request) -> JsonResponse:
        """
        Feed the dashboard's charts and tables.

        Separated from the shell so the page paints immediately and the
        (heavier) aggregate queries land afterwards.
        """
        days = _requested_days(request)
        start, end = reports.date_range(days)

        return JsonResponse({
            'range': {'start': start.isoformat(), 'end': end.isoformat(), 'days': days},
            'summary': reports.summary(start, end),
            'series': reports.time_series(start, end),
            'top_paths': reports.breakdown(start, end, 'path'),
            'countries': reports.breakdown(start, end, 'country'),
            'devices': reports.breakdown(start, end, 'device_type'),
            'channels': reports.breakdown(start, end, 'channel'),
            'referrers': reports.top_referrers(start, end),
            'web_vitals': reports.web_vitals_p75(start, end),
            'zero_result_searches': reports.zero_result_searches(start, end),
            'security': reports.security_summary(start, end),
            'not_found': reports.not_found_paths(start, end),
            'bots': reports.bot_split(start, end),
            'live': reports.live_visitor_count(),
        }, encoder=_DateAwareEncoder)


def _requested_days(request) -> int:
    """Read the date-range selector, clamped so a hand-edited URL cannot ask for years."""
    try:
        days = int(request.GET.get('days', get_setting('DASHBOARD_DEFAULT_DAYS')))
    except (TypeError, ValueError):
        days = get_setting('DASHBOARD_DEFAULT_DAYS')
    return max(1, min(days, 365))


class _DateAwareEncoder(json.JSONEncoder):
    """Serialises the date and Decimal values the report queries return."""

    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)
