"""
The raw IP address listing, plus a backfill of the addresses ``api.Visitor``
already holds.

Migration 0003 imported the legacy rows in hashed and truncated form, because
at that point the app stored no address in the clear. The site owner then asked
for the address listing back, so this migration also copies the original
addresses across — but only where they still exist.

Ordering matters and is enforced by ``run_before`` below: ``api.0003`` drops the
legacy table, and once it has run these addresses are gone for good. On any
database where ``api.0003`` has already been applied the backfill finds nothing
and does nothing, which is the correct outcome rather than an error.
"""
from django.db import migrations, models

BATCH_SIZE = 500


def backfill_legacy_addresses(apps, schema_editor):
    """
    Copy raw addresses out of api.Visitor, if that table is still present.

    Guarded on the table actually existing: the model is still in the migration
    state at this point even on a database where api.0003 has already dropped
    it, so a plain query would raise instead of finding zero rows.
    """
    connection = schema_editor.connection
    legacy_table = 'api_visitor'
    if legacy_table not in connection.introspection.table_names():
        return

    LegacyVisitor = apps.get_model('api', 'Visitor')
    VisitorIP = apps.get_model('analytics', 'VisitorIP')

    rows = [
        VisitorIP(
            ip_address=legacy.ip_address,
            is_public=legacy.is_public,
            visit_count=legacy.visit_count,
            first_seen_at=legacy.first_seen,
            last_seen_at=legacy.last_seen,
            last_path=(legacy.last_path or '')[:200],
            last_user_agent=(legacy.last_user_agent or '')[:300],
            country='',
            is_bot=_looks_automated(legacy.last_user_agent),
        )
        for legacy in LegacyVisitor.objects.all().iterator(chunk_size=BATCH_SIZE)
    ]

    # ignore_conflicts so re-running against a partly populated table is safe.
    VisitorIP.objects.bulk_create(rows, batch_size=BATCH_SIZE, ignore_conflicts=True)


def _looks_automated(user_agent):
    """
    Minimal bot detection, deliberately not importing analytics.useragent.

    A data migration has to keep producing the same result years from now, and
    pinning it to whatever the live parser happens to do would break that.
    """
    lowered = (user_agent or '').lower()
    if not lowered:
        return True
    return any(
        token in lowered
        for token in ('bot', 'crawl', 'spider', 'slurp', 'curl', 'wget', 'python-requests')
    )


def discard_addresses(apps, schema_editor):
    """Reversing drops the table, so there is nothing to undo row by row."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0003_migrate_legacy_visitors'),
    ]

    # api.0003 destroys the only copy of these addresses. Declared here rather
    # than as a dependency inside api.0003 so the coupling lives on the
    # analytics side and disappears with the app.
    run_before = [
        ('api', '0003_delete_visitor'),
    ]

    operations = [
        migrations.CreateModel(
            name='VisitorIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(db_index=True, unique=True)),
                ('is_public', models.BooleanField(db_index=True, default=False, help_text='Whether the address is routable on the public internet. Loopback and private ranges say nothing about where a visitor came from.')),
                ('visit_count', models.PositiveIntegerField(default=0)),
                ('first_seen_at', models.DateTimeField(db_index=True)),
                ('last_seen_at', models.DateTimeField(db_index=True)),
                ('last_path', models.CharField(blank=True, max_length=200)),
                ('last_user_agent', models.CharField(blank=True, max_length=300)),
                ('country', models.CharField(blank=True, db_index=True, max_length=2)),
                ('is_bot', models.BooleanField(db_index=True, default=False)),
            ],
            options={
                'verbose_name': 'Visitor IP address',
                'verbose_name_plural': 'Visitor IP addresses',
                'ordering': ['-last_seen_at'],
                'indexes': [models.Index(fields=['is_public', '-last_seen_at'], name='analytics_ip_public'), models.Index(fields=['is_bot', '-last_seen_at'], name='analytics_ip_bot')],
            },
        ),
        migrations.RunPython(backfill_legacy_addresses, discard_addresses),
    ]
