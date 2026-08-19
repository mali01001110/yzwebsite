"""
Generate synthetic traffic, to prove the dashboard's performance claim.

The requirement is that the admin dashboard renders in under 500 ms at a
million pageview rows. That is only demonstrable against a million rows, so
this builds them::

    python manage.py seed_analytics --pageviews 1000000
    python manage.py rebuild_stats --start 2026-05-01 --end 2026-08-19
    python manage.py seed_analytics --benchmark

Writes with ``bulk_create`` and no per-row Python work beyond choosing a
weighted random value, so a million rows is minutes rather than hours.

Never run against production. The command refuses unless ``--yes`` is passed.
"""
from __future__ import annotations

import random
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from analytics.defaults import get_setting
from analytics.models import (
    Channel,
    DailyStat,
    DeviceType,
    Event,
    PageView,
    Session,
    Visitor,
)
from analytics.privacy import hash_ip

BATCH_SIZE = 5_000

COUNTRIES = ['CI', 'FR', 'US', 'GB', 'DE', 'NG', 'GH', 'CA', 'IN', 'BR']
BROWSERS = [('Chrome', '130'), ('Safari', '18'), ('Firefox', '132'), ('Edge', '130')]
OPERATING_SYSTEMS = [('Windows', '10/11'), ('macOS', '14.6'), ('Android', '15'), ('iOS', '18')]
DEVICES = [DeviceType.DESKTOP] * 5 + [DeviceType.MOBILE] * 4 + [DeviceType.TABLET]
CHANNELS = (
    [Channel.DIRECT] * 4 + [Channel.ORGANIC] * 3 + [Channel.SOCIAL] * 2 + [Channel.REFERRAL]
)
REFERRER_HOSTS = ['', '', 'google.com', 'linkedin.com', 'github.com', 'news.ycombinator.com']
VITALS = [('LCP', 800, 4000), ('INP', 40, 500), ('CLS', 0, 1), ('TTFB', 80, 900), ('FCP', 400, 2500)]


class Command(BaseCommand):
    help = 'Generate synthetic analytics data, or benchmark the dashboard queries.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--pageviews', type=int, default=100_000)
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--visitors', type=int, default=0,
                            help='Distinct visitors. Defaults to pageviews // 8.')
        parser.add_argument('--yes', action='store_true',
                            help='Required. Confirms this is not a production database.')
        parser.add_argument('--benchmark', action='store_true',
                            help='Time the dashboard queries and exit.')
        parser.add_argument('--clear', action='store_true',
                            help='Delete all analytics rows before seeding.')

    def handle(self, *args, **options) -> None:
        if options['benchmark']:
            self._benchmark()
            return

        if not options['yes']:
            raise CommandError(
                'Refusing to write synthetic data without --yes. This command '
                'is destructive to the meaning of your statistics.'
            )

        if options['clear']:
            self._clear()

        self._seed(
            pageview_count=options['pageviews'],
            days=options['days'],
            visitor_count=options['visitors'] or max(options['pageviews'] // 8, 1),
        )

    def _clear(self) -> None:
        self.stdout.write('Clearing existing analytics rows…')
        for model in (Event, PageView, Session, Visitor, DailyStat):
            model.objects.all().delete()

    def _seed(self, pageview_count: int, days: int, visitor_count: int) -> None:
        started = time.perf_counter()
        now = timezone.now()
        window_seconds = days * 86_400
        random.seed(20260819)

        self.stdout.write(f'Creating {visitor_count:,} visitors…')
        visitor_ids = self._create_visitors(visitor_count, now, window_seconds)

        self.stdout.write(f'Creating {visitor_count:,} sessions…')
        session_ids = self._create_sessions(visitor_ids, now, window_seconds)

        self.stdout.write(f'Creating {pageview_count:,} pageviews…')
        self._create_pageviews(session_ids, pageview_count, now, window_seconds)

        self.stdout.write('Creating web-vital events…')
        self._create_vitals(session_ids, now, window_seconds)

        elapsed = time.perf_counter() - started
        self.stdout.write(self.style.SUCCESS(f'Seeded in {elapsed:.1f}s.'))
        self.stdout.write('Now run: python manage.py rebuild_stats --days ' + str(days))

    def _create_visitors(self, count: int, now, window: int) -> list[int]:
        created: list[int] = []
        batch: list[Visitor] = []
        for index in range(count):
            seen = now - timedelta(seconds=random.randint(0, window))
            batch.append(Visitor(
                visitor_id=f'seed{index:059d}'[:64],
                first_seen_at=seen,
                last_seen_at=seen + timedelta(minutes=random.randint(0, 30)),
                is_bot=random.random() < 0.08,
            ))
            if len(batch) >= BATCH_SIZE:
                created += [v.pk for v in Visitor.objects.bulk_create(batch)]
                batch = []
        if batch:
            created += [v.pk for v in Visitor.objects.bulk_create(batch)]
        return created

    def _create_sessions(self, visitor_ids: list[int], now, window: int) -> list[int]:
        created: list[int] = []
        batch: list[Session] = []
        for visitor_id in visitor_ids:
            started = now - timedelta(seconds=random.randint(0, window))
            browser, browser_version = random.choice(BROWSERS)
            os_name, os_version = random.choice(OPERATING_SYSTEMS)
            batch.append(Session(
                visitor_id=visitor_id,
                started_at=started,
                ended_at=started + timedelta(seconds=random.randint(5, 900)),
                landing_path='/',
                exit_path=random.choice(_section_paths()),
                referrer_host=random.choice(REFERRER_HOSTS),
                channel=random.choice(CHANNELS),
                country=random.choice(COUNTRIES),
                device_type=random.choice(DEVICES),
                browser=browser,
                browser_version=browser_version,
                os=os_name,
                os_version=os_version,
                ip_hash=hash_ip(f'198.51.100.{random.randint(1, 254)}'),
                ip_truncated='198.51.100.0',
                language='en-US',
                is_bot=random.random() < 0.08,
                pageview_count=random.randint(1, 12),
                duration_seconds=random.randint(0, 900),
                is_bounce=random.random() < 0.45,
            ))
            if len(batch) >= BATCH_SIZE:
                created += [s.pk for s in Session.objects.bulk_create(batch)]
                batch = []
        if batch:
            created += [s.pk for s in Session.objects.bulk_create(batch)]
        return created

    def _create_pageviews(self, session_ids: list[int], count: int, now, window: int) -> None:
        paths = _section_paths()
        batch: list[PageView] = []
        written = 0

        for _ in range(count):
            batch.append(PageView(
                session_id=random.choice(session_ids),
                path=random.choice(paths),
                occurred_at=now - timedelta(seconds=random.randint(0, window)),
                engaged_seconds=random.randint(0, 180),
                max_scroll_depth=random.choice([25, 50, 75, 100]),
                status_code=200 if random.random() > 0.02 else 404,
                response_ms=random.randint(8, 300),
                is_spa_navigation=random.random() > 0.3,
            ))
            if len(batch) >= BATCH_SIZE:
                PageView.objects.bulk_create(batch)
                written += len(batch)
                batch = []
                if written % 100_000 == 0:
                    self.stdout.write(f'  {written:,}…')
        if batch:
            PageView.objects.bulk_create(batch)

    def _create_vitals(self, session_ids: list[int], now, window: int) -> None:
        sample = random.sample(session_ids, min(len(session_ids), 5_000))
        batch = []
        for session_id in sample:
            metric, low, high = random.choice(VITALS)
            batch.append(Event(
                session_id=session_id,
                name='web_vital',
                props={'metric': metric},
                value=round(random.uniform(low, high), 2),
                occurred_at=now - timedelta(seconds=random.randint(0, window)),
            ))
        Event.objects.bulk_create(batch, batch_size=BATCH_SIZE)

    def _benchmark(self) -> None:
        """Time each dashboard query, and report the total against the 500 ms budget."""
        from analytics import reports

        start, end = reports.date_range(get_setting('DASHBOARD_DEFAULT_DAYS'))
        self.stdout.write(f'PageView rows:  {PageView.objects.count():,}')
        self.stdout.write(f'DailyStat rows: {DailyStat.objects.count():,}')
        self.stdout.write(f'Window:         {start} to {end}\n')

        checks = [
            ('summary', lambda: reports.summary(start, end)),
            ('time_series', lambda: reports.time_series(start, end)),
            ('top_paths', lambda: reports.breakdown(start, end, 'path')),
            ('countries', lambda: reports.breakdown(start, end, 'country')),
            ('devices', lambda: reports.breakdown(start, end, 'device_type')),
            ('channels', lambda: reports.breakdown(start, end, 'channel')),
            ('referrers', lambda: reports.top_referrers(start, end)),
            ('live_count', reports.live_visitor_count),
            ('web_vitals_p75', lambda: reports.web_vitals_p75(start, end)),
            ('zero_result_searches', lambda: reports.zero_result_searches(start, end)),
            ('security_summary', lambda: reports.security_summary(start, end)),
            ('not_found', lambda: reports.not_found_paths(start, end)),
            ('bot_split', lambda: reports.bot_split(start, end)),
        ]

        total_ms = 0.0
        for name, query in checks:
            queries_before = len(connection.queries_log)
            began = time.perf_counter()
            query()
            elapsed_ms = (time.perf_counter() - began) * 1000
            total_ms += elapsed_ms
            self.stdout.write(
                f'  {name:<24} {elapsed_ms:7.1f} ms  '
                f'({len(connection.queries_log) - queries_before} queries)'
            )

        style = self.style.SUCCESS if total_ms < 500 else self.style.ERROR
        self.stdout.write(style(f'\nTotal: {total_ms:.1f} ms (budget 500 ms)'))


def _section_paths() -> list[str]:
    """The site's real paths: '/' plus one anchor per navigation section."""
    return ['/'] + [f'/#{section}' for section in get_setting('SECTION_ALLOWLIST')]
