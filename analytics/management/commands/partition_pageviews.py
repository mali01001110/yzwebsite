"""
Convert PageView to a monthly-partitioned table, or inspect the result.

    python manage.py partition_pageviews --status
    python manage.py partition_pageviews --convert --yes
    python manage.py partition_pageviews --ensure
    python manage.py partition_pageviews --drop-legacy --yes

Conversion rewrites every row in the largest table in the schema. Run it with
the site quiesced, against a database you have just backed up, and read
``analytics/partitioning.py`` first — it documents each step and why the
primary key has to change.

At this site's volume this is not needed and not recommended. It exists so the
option is there when volume justifies it, which is somewhere north of 50
million rows.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from analytics import partitioning
from analytics.defaults import get_setting


class Command(BaseCommand):
    help = 'Manage monthly declarative partitioning of the PageView table.'

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--status', action='store_true', help='Report the current state.')
        group.add_argument('--convert', action='store_true', help='Convert the table. One-time.')
        group.add_argument('--ensure', action='store_true', help='Create any missing partitions.')
        group.add_argument('--drop-legacy', action='store_true',
                           help='Drop the pre-conversion table, once it is empty.')
        parser.add_argument('--yes', action='store_true', help='Confirm a destructive step.')
        parser.add_argument('--batch-size', type=int, default=50_000)

    def handle(self, *args, **options) -> None:
        if not partitioning.is_supported():
            raise CommandError('Partitioning requires PostgreSQL.')

        if options['status']:
            self._status()
        elif options['ensure']:
            self._ensure()
        elif options['convert']:
            self._convert(options['yes'], options['batch_size'])
        else:
            self._drop_legacy(options['yes'])

    def _status(self) -> None:
        state = partitioning.status()
        self.stdout.write(f'PARTITION_PAGEVIEWS setting: {state["enabled"]}')
        self.stdout.write(f'Table is partitioned:        {state["partitioned"]}')
        if not state['partitions']:
            self.stdout.write('No partitions.')
            return
        self.stdout.write('\nPartitions (estimated rows):')
        for name, rows in state['partitions']:
            self.stdout.write(f'  {name:<40} {rows:>12,}')

    def _ensure(self) -> None:
        created = partitioning.ensure_partitions()
        if not created:
            self.stdout.write(self.style.WARNING('Table is not partitioned; nothing to do.'))
            return
        self.stdout.write(self.style.SUCCESS(f'Ensured {len(created)} partition(s).'))

    def _convert(self, confirmed: bool, batch_size: int) -> None:
        if not get_setting('PARTITION_PAGEVIEWS'):
            raise CommandError(
                "Set ANALYTICS['PARTITION_PAGEVIEWS'] = True before converting, so "
                'the running application and the schema agree.'
            )
        if not confirmed:
            raise CommandError(
                'Conversion rewrites every row in the PageView table. Back up the '
                'database, stop write traffic, then re-run with --yes.'
            )

        result = partitioning.convert(batch_size=batch_size)
        if result.get('already_partitioned'):
            self.stdout.write(self.style.WARNING('Already partitioned; nothing to do.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Converted. {result["copied"]:,} of {result["total"]:,} row(s) copied.'
        ))
        self.stdout.write(
            'The pre-conversion table is kept as a safety net. Verify the row '
            'counts, then run --drop-legacy --yes.'
        )

    def _drop_legacy(self, confirmed: bool) -> None:
        if not confirmed:
            raise CommandError('Re-run with --yes to drop the pre-conversion table.')
        partitioning.drop_legacy_table()
        self.stdout.write(self.style.SUCCESS('Legacy table dropped.'))
