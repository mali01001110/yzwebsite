"""
Carry the rows collected by ``api.Visitor`` into the new schema.

``api.Visitor`` stored one aggregated row per raw IP address. The new schema
forbids a raw IP at rest and keys visitors on a salt that rotates every 24
hours. Those two facts have a consequence worth stating plainly:

**The historical salts never existed, so a legacy row's identifier cannot be
reconstructed.** Each one is therefore hashed with the fixed ``LEGACY_SALT``
below, and will never deduplicate against a visitor recorded after the cutover.
Somebody who visited before and after the change appears as two visitors. This
is inherent to switching to a rotating identifier, not a shortcut — the
alternative is keeping the raw addresses, which is the thing the new model
exists to stop.

What is preserved: when each address was first and last seen, how many
pageviews it accounted for, the last path it touched, and what its user agent
said about its browser. What is discarded: the address itself.

Reverse is a genuine no-op. The legacy table is dropped by ``api``'s own
migration, so there is nothing to restore into, and rebuilding raw addresses
from hashes is impossible by design.
"""
from django.db import migrations

# Fixed, and deliberately not derived from SECRET_KEY: a value that changed
# with the deployment would make this migration non-deterministic, producing
# different identifiers on every environment it ran in.
LEGACY_SALT = 'analytics-legacy-import-v1'

BATCH_SIZE = 500


def _hash(value, salt=LEGACY_SALT):
    import hashlib
    import hmac

    return hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest()[:64]


def _truncate_ip(raw):
    import ipaddress

    try:
        parsed = ipaddress.ip_address(raw.strip().strip('[]'))
    except (ValueError, AttributeError):
        return None
    prefix = 24 if parsed.version == 4 else 48
    return str(ipaddress.ip_network(f'{parsed}/{prefix}', strict=False).network_address)


def _classify_user_agent(user_agent):
    """
    Minimal browser/OS/device identification for legacy rows.

    Deliberately not importing ``analytics.useragent``: a data migration must
    keep producing the same result years from now, and pinning it to whatever
    the parser happens to do at that point would break that.
    """
    lowered = (user_agent or '').lower()

    browser = ''
    for name, token in (
        ('Edge', 'edg/'), ('Opera', 'opr/'), ('Chrome', 'chrome/'),
        ('Firefox', 'firefox/'), ('Safari', 'safari/'),
    ):
        if token in lowered:
            browser = name
            break

    operating_system = ''
    for name, token in (
        ('Android', 'android'), ('iOS', 'iphone'), ('iPadOS', 'ipad'),
        ('Windows', 'windows'), ('macOS', 'mac os x'), ('Linux', 'linux'),
    ):
        if token in lowered:
            operating_system = name
            break

    is_bot = any(
        token in lowered
        for token in ('bot', 'crawl', 'spider', 'slurp', 'curl', 'wget', 'python-requests')
    ) or not lowered

    if is_bot:
        device = 'bot'
    elif any(token in lowered for token in ('ipad', 'tablet')):
        device = 'tablet'
    elif any(token in lowered for token in ('mobi', 'android', 'iphone')):
        device = 'mobile'
    elif lowered:
        device = 'desktop'
    else:
        device = 'unknown'

    return browser, operating_system, device, is_bot


def import_legacy_visitors(apps, schema_editor):
    LegacyVisitor = apps.get_model('api', 'Visitor')
    Visitor = apps.get_model('analytics', 'Visitor')
    Session = apps.get_model('analytics', 'Session')

    legacy_rows = LegacyVisitor.objects.all().order_by('pk')
    if not legacy_rows.exists():
        return

    visitors = []
    pending = []

    for row in legacy_rows.iterator(chunk_size=BATCH_SIZE):
        browser, operating_system, device, is_bot = _classify_user_agent(row.last_user_agent)
        visitor_id = _hash(f'{row.ip_address}|{row.last_user_agent}')

        visitors.append(
            Visitor(
                visitor_id=visitor_id,
                first_seen_at=row.first_seen,
                last_seen_at=row.last_seen,
                is_bot=is_bot,
            )
        )
        pending.append((visitor_id, row, browser, operating_system, device, is_bot))

    # ignore_conflicts: two legacy addresses sharing a user agent would collide
    # only if they were the same address, but the import must not fail if the
    # migration is somehow re-run against a partially populated table.
    Visitor.objects.bulk_create(visitors, batch_size=BATCH_SIZE, ignore_conflicts=True)

    stored = {v.visitor_id: v for v in Visitor.objects.filter(
        visitor_id__in=[item[0] for item in pending]
    )}

    sessions = []
    for visitor_id, row, browser, operating_system, device, is_bot in pending:
        visitor = stored.get(visitor_id)
        if visitor is None:
            continue

        # The legacy row recorded a first and last sighting but no session
        # boundaries, so its whole history collapses into one synthetic session
        # spanning that range. Marked closed, because it certainly is.
        sessions.append(
            Session(
                visitor=visitor,
                started_at=row.first_seen,
                ended_at=row.last_seen,
                landing_path=(row.last_path or '')[:200],
                exit_path=(row.last_path or '')[:200],
                channel='direct',
                ip_hash=_hash(row.ip_address),
                ip_truncated=_truncate_ip(row.ip_address),
                browser=browser,
                os=operating_system,
                device_type=device,
                is_bot=is_bot,
                bot_reason='legacy import' if is_bot else '',
                pageview_count=row.visit_count,
                duration_seconds=max(
                    int((row.last_seen - row.first_seen).total_seconds()), 0
                ),
                is_bounce=row.visit_count <= 1,
            )
        )

    Session.objects.bulk_create(sessions, batch_size=BATCH_SIZE)


def reverse_import(apps, schema_editor):
    """
    Intentionally a no-op.

    The raw addresses these rows came from were discarded on the way in, so
    there is nothing to restore. Rolling this migration back leaves the
    imported rows in place rather than deleting data that cannot be recreated.
    """
    return


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_postgres_indexes'),
        ('api', '0002_visitor'),
    ]

    # Without this the graph is free to drop api.Visitor first, since nothing
    # else orders the two migrations against each other — and the import would
    # then run against a table that no longer exists. Declared here rather than
    # as a dependency inside api.0003 so the coupling lives on the analytics
    # side and disappears with the app.
    run_before = [
        ('api', '0003_delete_visitor'),
    ]

    operations = [
        migrations.RunPython(import_legacy_visitors, reverse_import),
    ]
