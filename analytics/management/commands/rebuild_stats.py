"""Rebuild the DailyStat rollup for a date range."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from analytics.pipeline import rebuild_stats


class Command(BaseCommand):
    help = (
        'Rebuild pre-aggregated DailyStat rows from the raw tables. Idempotent: '
        'each date is deleted and rewritten, so re-running any range is safe.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--start',
            type=_parse_date,
            help='First date to rebuild (YYYY-MM-DD). Defaults to --days ago.',
        )
        parser.add_argument(
            '--end',
            type=_parse_date,
            help='Last date to rebuild (YYYY-MM-DD). Defaults to today.',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=2,
            help='Rebuild this many days back from --end. Ignored when --start is given.',
        )

    def handle(self, *args, **options) -> None:
        end: date = options['end'] or timezone.now().date()
        start: date = options['start'] or end - timedelta(days=max(options['days'] - 1, 0))

        if start > end:
            raise CommandError('--start must not be after --end.')

        self.stdout.write(f'Rebuilding DailyStat from {start} to {end}…')
        rows = rebuild_stats(start, end)
        self.stdout.write(self.style.SUCCESS(f'Wrote {rows} DailyStat row(s).'))


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise CommandError(f'Not a valid date: {value!r}. Expected YYYY-MM-DD.')
