"""Rebuild pageviews from a gunicorn access log for a period that was lost."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Iterable, Iterator, TextIO

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics import accesslog
from analytics.buffer import KIND_PAGEVIEW, buffer, record
from analytics.defaults import get_setting
from analytics.models import Session
from analytics.pipeline import flush, rebuild_stats, sessionize

# Records are flushed in batches rather than buffered whole: a long log would
# otherwise sit in memory in its entirety, and the buffer would start evicting
# from the left once it passed BUFFER_HARD_LIMIT, losing the oldest lines of
# the very import meant to recover them.
BATCH_SIZE = 400


class Command(BaseCommand):
    help = (
        'Reconstruct PageView, Session and Visitor rows from a gunicorn access '
        'log, for traffic that was served but never recorded. Imported sessions '
        f'are marked with import_source="{accesslog.DEFAULT_IMPORT_SOURCE}"; '
        'visitor identity is synthesised and IP addresses are not recoverable. '
        'Idempotent: rows from a previous import of the same source and dates '
        'are removed before writing.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            'paths',
            nargs='*',
            help='Access log files. Reads standard input when none are given.',
        )
        parser.add_argument(
            '--import-source',
            default=accesslog.DEFAULT_IMPORT_SOURCE,
            help=(
                'Marker written to Session.import_source, and the key this '
                'command deletes by when re-importing. Must not be empty, '
                'which is what recorded traffic uses.'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be imported without writing anything.',
        )
        parser.add_argument(
            '--keep-existing',
            action='store_true',
            help=(
                'Do not delete previously imported rows first. Re-running then '
                'duplicates them; only useful when appending a log that covers '
                'a period the earlier import did not.'
            ),
        )

    def handle(self, *args, **options) -> None:
        import_source = options['import_source'].strip()
        if not import_source:
            raise CommandError(
                '--import-source must not be empty: recorded traffic is what '
                'carries an empty import_source, and reusing it would make the '
                'reconstructed rows indistinguishable.'
            )

        entries = list(self._read_entries(options['paths']))
        # Sorted because sessionization assumes records arrive in the order the
        # requests happened, which is true of live traffic and false of an
        # exported log: Render's log view hands them back newest first, and
        # feeding that straight in merges visits hours apart into one session
        # that starts after some of its own pageviews.
        pageviews = sorted(
            (entry for entry in entries if accesslog.is_pageview(entry)),
            key=lambda entry: entry.occurred_at,
        )

        self.stdout.write(
            f'Parsed {len(entries)} request(s); {len(pageviews)} are pageviews.'
        )
        if not pageviews:
            self.stdout.write(self.style.WARNING('Nothing to import.'))
            return

        covered = sorted({entry.occurred_at.date() for entry in pageviews})
        self.stdout.write(f'Dates covered: {covered[0]} to {covered[-1]}.')

        if options['dry_run']:
            self._report_dry_run(pageviews)
            return

        if not options['keep_existing']:
            removed = self._delete_previous_import(import_source, covered[0], covered[-1])
            if removed:
                self.stdout.write(f'Removed {removed} session(s) from an earlier import.')

        written = self._import(pageviews, import_source)
        self.stdout.write(self.style.SUCCESS(f'Wrote {written} pageview row(s).'))

        # Sessions are closed and rolled up here rather than left to the
        # scheduler, so the dashboard reflects the import as soon as it ends.
        sessionize()
        rows = rebuild_stats(covered[0], covered[-1])
        self.stdout.write(self.style.SUCCESS(f'Rebuilt {rows} DailyStat row(s).'))

        self.stdout.write(
            'IP addresses were not recoverable from the log, so no VisitorIP '
            'rows were created and unique-visitor counts are a floor.'
        )

    def _read_entries(self, paths: list[str]) -> Iterator[accesslog.AccessLogEntry]:
        if not paths:
            yield from self._parse(sys.stdin)
            return

        for path in paths:
            try:
                with open(path, encoding='utf-8', errors='replace') as handle:
                    yield from self._parse(handle)
            except OSError as error:
                raise CommandError(f'Could not read {path}: {error}') from error

    @staticmethod
    def _parse(handle: TextIO) -> Iterator[accesslog.AccessLogEntry]:
        for line in handle:
            entry = accesslog.parse_line(line)
            if entry is not None:
                yield entry

    def _import(
        self, pageviews: list[accesslog.AccessLogEntry], import_source: str
    ) -> int:
        """
        Feed the entries through the live write path, a batch at a time.

        Deliberately not a bulk_create of its own: routing through the buffer
        means sessionization, channel classification, user-agent parsing and
        bot scoring are the same code that writes real traffic, so an imported
        row differs from a recorded one only in what the log could not say.
        """
        buffer.clear()
        written = 0

        for batch in _session_safe_batches(pageviews):
            for entry in batch:
                record(KIND_PAGEVIEW, **accesslog.to_record(entry, import_source))
            written += flush()

        return written

    def _delete_previous_import(
        self, import_source: str, start: date, end: date
    ) -> int:
        """
        Remove an earlier import of the same source over the same dates.

        Scoped to the marker, so recorded traffic in the same window is never
        touched. Pageviews and events go with their sessions by cascade.
        """
        with transaction.atomic():
            sessions = Session.objects.filter(
                import_source=import_source,
                started_at__date__gte=start,
                started_at__date__lt=end + timedelta(days=1),
            )
            _, by_model = sessions.delete()
        return by_model.get('analytics.Session', 0)

    def _report_dry_run(self, pageviews: list[accesslog.AccessLogEntry]) -> None:
        by_path: dict[str, int] = {}
        for entry in pageviews:
            by_path[entry.path] = by_path.get(entry.path, 0) + 1

        self.stdout.write('Top paths that would be imported:')
        for path, count in sorted(by_path.items(), key=lambda row: -row[1])[:20]:
            self.stdout.write(f'  {count:>6}  {path}')
        self.stdout.write(self.style.WARNING('Dry run: nothing was written.'))


def _session_safe_batches(
    entries: list[accesslog.AccessLogEntry],
) -> Iterable[list[accesslog.AccessLogEntry]]:
    """
    Split chronological entries into batches that no session boundary crosses.

    ``_resolve_sessions`` attaches every record a visitor has in one flush to a
    single session. That is right for live traffic, where a batch covers a few
    seconds, and wrong for an import, where one batch can cover days: the whole
    span would collapse into a single session that starts after some of its own
    pageviews. Cutting the batch whenever a visitor reappears past the
    inactivity timeout hands the resolver the same guarantee live traffic gives
    it for free, so the session boundaries come out of the ordinary rule rather
    than out of a second implementation of it here.
    """
    timeout = timedelta(minutes=get_setting('SESSION_TIMEOUT_MINUTES'))
    batch: list[accesslog.AccessLogEntry] = []
    last_seen: dict[str, object] = {}

    for entry in entries:
        visitor_id = accesslog.synthetic_visitor_id(entry.user_agent, entry.occurred_at)
        previous = last_seen.get(visitor_id)
        gap_closes_session = (
            previous is not None and entry.occurred_at - previous >= timeout
        )

        if batch and (len(batch) >= BATCH_SIZE or gap_closes_session):
            yield batch
            batch = []
            last_seen = {}

        batch.append(entry)
        last_seen[visitor_id] = entry.occurred_at

    if batch:
        yield batch
