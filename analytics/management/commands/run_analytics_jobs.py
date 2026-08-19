"""
Run the pipeline's periodic jobs once, from outside the web process.

This is the escape hatch from the in-process scheduler. With
``ANALYTICS['RUN_INLINE_SCHEDULER'] = False`` the web service stops running
these itself and something external — Render Cron, a GitHub Actions schedule,
an ordinary crontab — calls this command instead. Nothing else changes.

Suggested schedule if you move to cron:

    */5  * * * *   python manage.py run_analytics_jobs --flush --sessionize
    17   * * * *   python manage.py run_analytics_jobs --rollup
    40   3 * * *   python manage.py run_analytics_jobs --retention
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from analytics import pipeline


class Command(BaseCommand):
    help = 'Run analytics maintenance jobs once. With no flags, runs all of them.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--flush', action='store_true', help='Write the buffered records.')
        parser.add_argument('--sessionize', action='store_true', help='Close idle sessions.')
        parser.add_argument('--rollup', action='store_true', help='Roll up today and yesterday.')
        parser.add_argument('--retention', action='store_true', help='Delete expired raw rows.')

    def handle(self, *args, **options) -> None:
        selected = [name for name in ('flush', 'sessionize', 'rollup', 'retention')
                    if options[name]]
        if not selected:
            selected = ['flush', 'sessionize', 'rollup', 'retention']

        for name in selected:
            self.stdout.write(f'Running {name}…')
            result = getattr(self, f'_{name}')()
            self.stdout.write(self.style.SUCCESS(f'  {name}: {result}'))

    def _flush(self):
        return f'{pipeline.flush()} row(s) written'

    def _sessionize(self):
        return f'{pipeline.sessionize()} session(s) closed'

    def _rollup(self):
        return f'{pipeline.rollup_recent()} DailyStat row(s)'

    def _retention(self):
        return pipeline.enforce_retention()
