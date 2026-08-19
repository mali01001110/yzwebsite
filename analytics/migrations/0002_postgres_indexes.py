"""
Postgres-only indexes for the append-only tables.

These are applied with raw SQL behind a vendor check rather than declared in
``Meta.indexes``, because ``BrinIndex`` and ``GinIndex`` cannot be created on
SQLite: declaring them on the models would make every migration in this app
unappliable on a SQLite connection, which is what local development and the
test suite currently use.

The trade-off is that Django's migration state does not know about these
indexes, so ``makemigrations`` will neither manage nor drop them. That is
acceptable for indexes — they carry no semantics the ORM needs — and the
alternative is either a Postgres-only test suite or no BRIN at all.

BRIN rather than B-tree on ``occurred_at``: these tables are append-only and
physically ordered by time, so a summary of the minimum and maximum value in
each block range answers a date filter while costing a few kilobytes, where a
B-tree over the same column would cost tens of megabytes per million rows.
"""
from django.db import migrations

# pages_per_range 32 rather than the default 128: it quadruples index size (to
# a still-negligible figure) in exchange for scanning a quarter as many heap
# pages per lookup, which is the right trade when the table is the largest one
# in the schema and the dashboard filters it on every query.
POSTGRES_INDEXES = [
    (
        'analytics_pv_brin',
        'CREATE INDEX IF NOT EXISTS analytics_pv_brin ON analytics_pageview '
        'USING BRIN (occurred_at) WITH (pages_per_range = 32)',
    ),
    (
        'analytics_ev_brin',
        'CREATE INDEX IF NOT EXISTS analytics_ev_brin ON analytics_event '
        'USING BRIN (occurred_at) WITH (pages_per_range = 32)',
    ),
    (
        'analytics_sec_brin',
        'CREATE INDEX IF NOT EXISTS analytics_sec_brin ON analytics_securityevent '
        'USING BRIN (occurred_at) WITH (pages_per_range = 32)',
    ),
    (
        'analytics_sq_brin',
        'CREATE INDEX IF NOT EXISTS analytics_sq_brin ON analytics_searchquery '
        'USING BRIN (occurred_at) WITH (pages_per_range = 32)',
    ),
    (
        # jsonb_path_ops rather than the default: roughly a third of the size
        # and faster for the containment queries (props @> '{...}') this index
        # exists to serve. It gives up key-existence operators (?, ?|, ?&),
        # which the dashboard does not use.
        'analytics_ev_props',
        'CREATE INDEX IF NOT EXISTS analytics_ev_props ON analytics_event '
        'USING GIN (props jsonb_path_ops)',
    ),
]


def create_postgres_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for _, statement in POSTGRES_INDEXES:
            cursor.execute(statement)


def drop_postgres_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for name, _ in POSTGRES_INDEXES:
            cursor.execute(f'DROP INDEX IF EXISTS {name}')


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_postgres_indexes, drop_postgres_indexes),
    ]
