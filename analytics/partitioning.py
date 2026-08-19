"""
Monthly declarative partitioning for ``PageView``.

Off by default and **not** wired into a migration, deliberately. Converting the
largest table in the schema is a one-time operation that rewrites every row; it
belongs behind an explicit command run against a quiesced site, not behind a
deploy that happens to include a migration.

Turn it on with ``ANALYTICS['PARTITION_PAGEVIEWS'] = True`` and then run
``python manage.py partition_pageviews --convert --yes``. Once converted, the
scheduler calls :func:`ensure_partitions` monthly so future months always exist
before rows need them.

When this is worth doing: at roughly 50–100 million rows, where a date-range
query stops being able to skip enough heap pages and index maintenance on
inserts starts to cost. At this site's ~500 pageviews/day that is decades away,
which is why it ships off.

Postgres only. Every function here returns without acting on other backends.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db import connection

from .defaults import get_setting
from .models import PageView

logger = logging.getLogger(__name__)

TABLE = PageView._meta.db_table
LEGACY_TABLE = f'{TABLE}_legacy'


def is_supported() -> bool:
    return connection.vendor == 'postgresql'


def is_partitioned() -> bool:
    """True when the table has already been converted."""
    if not is_supported():
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relkind FROM pg_class WHERE relname = %s", [TABLE]
        )
        row = cursor.fetchone()
    # 'p' is a partitioned table; 'r' is an ordinary one.
    return bool(row and row[0] == 'p')


def partition_name(month: date) -> str:
    return f'{TABLE}_y{month.year}m{month.month:02d}'


def month_bounds(month: date) -> tuple[date, date]:
    """Return the half-open [start, end) range for a month."""
    start = month.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def ensure_partitions(from_month: date | None = None, ahead: int | None = None) -> list[str]:
    """
    Create any missing monthly partitions. Idempotent and safe to re-run.

    Called by the scheduler once converted, so a month boundary can never
    arrive without somewhere to put the rows.
    """
    if not is_supported() or not is_partitioned():
        return []

    ahead = ahead if ahead is not None else get_setting('PARTITION_AHEAD_MONTHS')
    cursor_month = (from_month or date.today()).replace(day=1)

    created: list[str] = []
    with connection.cursor() as cursor:
        for _ in range(ahead + 1):
            name = partition_name(cursor_month)
            start, end = month_bounds(cursor_month)
            cursor.execute(
                f'CREATE TABLE IF NOT EXISTS {name} '
                f'PARTITION OF {TABLE} FOR VALUES FROM (%s) TO (%s)',
                [start, end],
            )
            created.append(name)
            cursor_month = end

    logger.info('Ensured %d PageView partition(s)', len(created))
    return created


def convert(batch_size: int = 50_000) -> dict[str, int]:
    """
    Convert the existing table into a partitioned one, preserving every row.

    The sequence, and why it is this order:

    1. Rename the current table out of the way. Its data is untouched.
    2. Create the partitioned parent with the same columns. The primary key
       must include ``occurred_at`` — Postgres requires the partition key in
       every unique constraint, which is why the PK becomes ``(id, occurred_at)``
       rather than ``(id)``.
    3. Create partitions spanning the full range of existing data.
    4. Copy rows across in batches, so a large table does not hold one
       transaction open for the whole operation.
    5. Leave the legacy table in place. Dropping it is a separate, deliberate
       step once the result has been verified — an automatic drop here would
       make a mistake unrecoverable.
    """
    if not is_supported():
        raise RuntimeError('Partitioning requires PostgreSQL.')
    if is_partitioned():
        return {'already_partitioned': 1}

    with connection.cursor() as cursor:
        cursor.execute(f'SELECT MIN(occurred_at), MAX(occurred_at), COUNT(*) FROM {TABLE}')
        earliest, latest, total = cursor.fetchone()

        cursor.execute(f'ALTER TABLE {TABLE} RENAME TO {LEGACY_TABLE}')

        # LIKE ... INCLUDING DEFAULTS copies column definitions without the
        # constraints, which is what we want: the PK has to be redefined to
        # include the partition key.
        cursor.execute(
            f'CREATE TABLE {TABLE} (LIKE {LEGACY_TABLE} INCLUDING DEFAULTS) '
            f'PARTITION BY RANGE (occurred_at)'
        )
        cursor.execute(
            f'ALTER TABLE {TABLE} ADD PRIMARY KEY (id, occurred_at)'
        )

        if total:
            month = earliest.date().replace(day=1)
            last = latest.date().replace(day=1)
            while month <= last:
                name = partition_name(month)
                start, end = month_bounds(month)
                cursor.execute(
                    f'CREATE TABLE IF NOT EXISTS {name} '
                    f'PARTITION OF {TABLE} FOR VALUES FROM (%s) TO (%s)',
                    [start, end],
                )
                month = end

    ensure_partitions()

    copied = _copy_rows(batch_size) if total else 0
    logger.info('Converted %s to a partitioned table; copied %d row(s)', TABLE, copied)
    return {'total': total or 0, 'copied': copied}


def _copy_rows(batch_size: int) -> int:
    """Move rows from the legacy table into the partitioned one, in batches."""
    copied = 0
    with connection.cursor() as cursor:
        while True:
            cursor.execute(
                f'WITH moved AS ('
                f'  DELETE FROM {LEGACY_TABLE} '
                f'  WHERE id IN (SELECT id FROM {LEGACY_TABLE} LIMIT %s) '
                f'  RETURNING *'
                f') INSERT INTO {TABLE} SELECT * FROM moved',
                [batch_size],
            )
            moved = cursor.rowcount
            copied += moved
            if moved < batch_size:
                return copied


def drop_legacy_table() -> bool:
    """Drop the pre-conversion table. Separate step, on purpose."""
    if not is_supported():
        return False
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT COUNT(*) FROM {LEGACY_TABLE}')
        remaining = cursor.fetchone()[0]
        if remaining:
            raise RuntimeError(
                f'{LEGACY_TABLE} still holds {remaining} row(s); refusing to drop it.'
            )
        cursor.execute(f'DROP TABLE IF EXISTS {LEGACY_TABLE}')
    return True


def status() -> dict:
    """Report the current partitioning state, for the management command."""
    if not is_supported():
        return {'supported': False, 'partitioned': False, 'partitions': []}

    partitions: list[tuple[str, int]] = []
    if is_partitioned():
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT c.relname, COALESCE(s.n_live_tup, 0) '
                'FROM pg_inherits i '
                'JOIN pg_class c ON c.oid = i.inhrelid '
                'LEFT JOIN pg_stat_user_tables s ON s.relname = c.relname '
                'WHERE i.inhparent = %s::regclass ORDER BY c.relname',
                [TABLE],
            )
            partitions = list(cursor.fetchall())

    return {
        'supported': True,
        'enabled': get_setting('PARTITION_PAGEVIEWS'),
        'partitioned': is_partitioned(),
        'partitions': partitions,
    }
