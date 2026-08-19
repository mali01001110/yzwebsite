"""
Storage for first-party visitor analytics.

Three shapes of table live here, and they have different rules:

* ``Visitor`` and ``Session`` are mutable summaries, updated as a visit unfolds.
* ``PageView``, ``Event`` and ``SecurityEvent`` are append-only time series.
  They carry BRIN indexes on their timestamp: rows arrive in timestamp order,
  so a block-range summary answers a date filter in a fraction of the space a
  B-tree would need. Those indexes, and the GIN index on ``Event.props``, are
  Postgres-only and are therefore created by migration ``0002`` behind a
  vendor check rather than declared in ``Meta.indexes`` — declaring them here
  would make every migration unappliable on SQLite.
* ``DailyStat`` is the pre-aggregated rollup. Admin charts read this and only
  this, so dashboard cost stays flat as the raw tables grow.

No raw IP address is ever stored. Every model that needs to identify an address
holds a salted hash plus a truncated form; see :mod:`analytics.privacy`.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Channel(models.TextChoices):
    """How a session arrived. Derived from the referrer and any utm_medium."""

    DIRECT = 'direct', 'Direct'
    ORGANIC = 'organic', 'Organic search'
    PAID = 'paid', 'Paid'
    SOCIAL = 'social', 'Social'
    REFERRAL = 'referral', 'Referral'
    EMAIL = 'email', 'Email'
    INTERNAL = 'internal', 'Internal'


class DeviceType(models.TextChoices):
    DESKTOP = 'desktop', 'Desktop'
    MOBILE = 'mobile', 'Mobile'
    TABLET = 'tablet', 'Tablet'
    BOT = 'bot', 'Bot'
    UNKNOWN = 'unknown', 'Unknown'


class SecurityEventKind(models.TextChoices):
    FAILED_LOGIN = 'failed_login', 'Failed login'
    RATE_LIMIT = 'rate_limit', 'Rate limit hit'
    PATH_SCAN = 'path_scan', 'Path scan'
    ENUMERATION = 'enumeration', 'ID enumeration'
    SUSPICIOUS_UA = 'suspicious_ua', 'Suspicious user agent'


class Visitor(models.Model):
    """
    One row per distinct visitor per day, keyed by a rotating salted hash.

    ``visitor_id`` is sha256(daily_salt + ip + user_agent). The salt rotates
    every 24 hours and old salts are discarded, which buys stable daily unique
    counts with no cookie and nothing at rest that can be reversed to an IP
    address. The deliberate cost is that the same person browsing on two
    consecutive days is two visitors.

    First-touch and last-touch attribution are stored side by side because they
    answer different questions: which channel found this person, and which
    channel brought them back.
    """

    ID_LENGTH = 64
    ATTRIBUTION_MAX_LENGTH = 120

    visitor_id = models.CharField(max_length=ID_LENGTH, unique=True, db_index=True)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_visitors',
        help_text='Attached on login, so an authenticated session can be '
                  'traced back to the anonymous activity that preceded it.',
    )
    is_bot = models.BooleanField(default=False, db_index=True)

    first_touch_channel = models.CharField(
        max_length=20, choices=Channel.choices, blank=True
    )
    first_touch_source = models.CharField(max_length=ATTRIBUTION_MAX_LENGTH, blank=True)
    first_touch_campaign = models.CharField(max_length=ATTRIBUTION_MAX_LENGTH, blank=True)
    last_touch_channel = models.CharField(
        max_length=20, choices=Channel.choices, blank=True
    )
    last_touch_source = models.CharField(max_length=ATTRIBUTION_MAX_LENGTH, blank=True)
    last_touch_campaign = models.CharField(max_length=ATTRIBUTION_MAX_LENGTH, blank=True)

    class Meta:
        ordering = ['-last_seen_at']
        indexes = [
            models.Index(fields=['-last_seen_at'], name='analytics_vis_lastseen'),
            models.Index(fields=['is_bot', '-last_seen_at'], name='analytics_vis_bot'),
        ]

    def __str__(self) -> str:
        return f'{self.visitor_id[:12]}…'


class Session(models.Model):
    """
    A contiguous run of activity from one visitor, closed after 30 idle minutes.

    Enrichment that is too slow for the request path — geo lookup, ASN lookup,
    user-agent parsing, bot scoring — lands here, written by the pipeline
    worker rather than by the middleware.
    """

    PATH_MAX_LENGTH = 200
    HOST_MAX_LENGTH = 120
    URL_MAX_LENGTH = 500
    UTM_MAX_LENGTH = 120
    HASH_LENGTH = 64

    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    landing_path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    exit_path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    referrer_host = models.CharField(max_length=HOST_MAX_LENGTH, blank=True)
    referrer_url = models.CharField(max_length=URL_MAX_LENGTH, blank=True)
    channel = models.CharField(
        max_length=20, choices=Channel.choices, default=Channel.DIRECT
    )

    utm_source = models.CharField(max_length=UTM_MAX_LENGTH, blank=True)
    utm_medium = models.CharField(max_length=UTM_MAX_LENGTH, blank=True)
    utm_campaign = models.CharField(max_length=UTM_MAX_LENGTH, blank=True)
    utm_term = models.CharField(max_length=UTM_MAX_LENGTH, blank=True)
    utm_content = models.CharField(max_length=UTM_MAX_LENGTH, blank=True)
    click_id = models.CharField(
        max_length=UTM_MAX_LENGTH,
        null=True,
        blank=True,
        help_text='gclid, fbclid or msclkid, whichever was present on landing.',
    )

    country = models.CharField(max_length=2, blank=True, db_index=True)
    region = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    longitude = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    tz_from_ip = models.CharField(max_length=64, blank=True)

    asn = models.CharField(max_length=16, blank=True)
    asn_org = models.CharField(max_length=160, blank=True)
    is_datacenter = models.BooleanField(default=False)

    browser = models.CharField(max_length=60, blank=True)
    browser_version = models.CharField(max_length=30, blank=True)
    os = models.CharField(max_length=60, blank=True)
    os_version = models.CharField(max_length=30, blank=True)
    device_type = models.CharField(
        max_length=10, choices=DeviceType.choices, default=DeviceType.UNKNOWN
    )

    ip_hash = models.CharField(max_length=HASH_LENGTH, blank=True, db_index=True)
    ip_truncated = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IPv4 with the last octet zeroed, IPv6 with the last 80 bits '
                  'zeroed. Coarse enough not to identify a household, precise '
                  'enough to group an abusive network.',
    )

    language = models.CharField(max_length=35, blank=True)
    is_bot = models.BooleanField(default=False, db_index=True)
    bot_reason = models.CharField(max_length=60, blank=True)

    pageview_count = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    is_bounce = models.BooleanField(default=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['visitor', '-started_at'], name='analytics_ses_visitor'),
            models.Index(fields=['-started_at', 'channel'], name='analytics_ses_channel'),
            models.Index(fields=['ended_at'], name='analytics_ses_open'),
            models.Index(fields=['is_bot', '-started_at'], name='analytics_ses_bot'),
        ]

    def __str__(self) -> str:
        return f'session {self.pk} · {self.visitor_id}'


class PageView(models.Model):
    """
    One page or section view. Append-only.

    On this site the SPA has a single route and navigates by anchor, so a
    section coming into view is recorded here as ``path='/#skills'`` with
    ``is_spa_navigation=True``. That keeps section reporting on the same index,
    the same rollup dimension and the same engagement fields as a real page,
    instead of inventing a parallel model for it.
    """

    PATH_MAX_LENGTH = 200
    TITLE_MAX_LENGTH = 200
    URL_MAX_LENGTH = 500
    HASH_LENGTH = 64

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='pageviews')
    path = models.CharField(max_length=PATH_MAX_LENGTH, db_index=True)
    query_hash = models.CharField(
        max_length=HASH_LENGTH,
        blank=True,
        help_text='Hash of the non-allowlisted query string. Never the raw '
                  'value, so a token pasted into a URL is not stored.',
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH, blank=True)
    referrer_url = models.CharField(max_length=URL_MAX_LENGTH, blank=True)
    occurred_at = models.DateTimeField(db_index=True)

    engaged_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Visible, interacted-with time from the beacon. Not wall '
                  'clock: a tab left open in the background accrues nothing.',
    )
    max_scroll_depth = models.PositiveSmallIntegerField(null=True, blank=True)
    status_code = models.PositiveSmallIntegerField(default=200)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    is_spa_navigation = models.BooleanField(default=False)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            # A BRIN index on occurred_at is added by migration 0002 on
            # Postgres. See the module docstring.
            models.Index(fields=['path', '-occurred_at'], name='analytics_pv_path'),
            models.Index(fields=['session', '-occurred_at'], name='analytics_pv_session'),
            models.Index(fields=['status_code'], name='analytics_pv_status'),
        ]

    def __str__(self) -> str:
        return f'{self.path} @ {self.occurred_at:%Y-%m-%d %H:%M}'


class Event(models.Model):
    """
    A named thing that happened, with arbitrary properties. Append-only.

    ``name`` is constrained to a registered allowlist at ingest rather than by a
    database constraint, so adding an event type is a settings change and not a
    migration.
    """

    NAME_MAX_LENGTH = 60

    session = models.ForeignKey(
        Session, null=True, blank=True, on_delete=models.CASCADE, related_name='events'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_events',
    )
    name = models.CharField(max_length=NAME_MAX_LENGTH, db_index=True)
    props = models.JSONField(default=dict, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            # BRIN on occurred_at and GIN on props are added by migration
            # 0002 on Postgres. See the module docstring.
            models.Index(fields=['name', '-occurred_at'], name='analytics_ev_name'),
            models.Index(fields=['session', '-occurred_at'], name='analytics_ev_session'),
        ]

    def __str__(self) -> str:
        return f'{self.name} @ {self.occurred_at:%Y-%m-%d %H:%M}'


class SecurityEvent(models.Model):
    """
    An abuse signal worth keeping even when the request itself was rejected.

    Recorded, never acted on: this app observes and reports, and deliberately
    does not block. Blocking is a separate decision with a separate blast
    radius.
    """

    HASH_LENGTH = 64
    PATH_MAX_LENGTH = 200

    kind = models.CharField(max_length=20, choices=SecurityEventKind.choices, db_index=True)
    ip_hash = models.CharField(max_length=HASH_LENGTH, blank=True, db_index=True)
    ip_truncated = models.GenericIPAddressField(null=True, blank=True)
    asn = models.CharField(max_length=16, blank=True)
    country = models.CharField(max_length=2, blank=True)
    path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    username_attempted = models.CharField(max_length=150, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['kind', '-occurred_at'], name='analytics_sec_kind'),
            models.Index(fields=['ip_hash', '-occurred_at'], name='analytics_sec_ip'),
        ]

    def __str__(self) -> str:
        return f'{self.get_kind_display()} @ {self.occurred_at:%Y-%m-%d %H:%M}'


class SearchQuery(models.Model):
    """
    An internal site search, and whether it led anywhere.

    Zero-result queries are the highest-signal report in the system: they are a
    list, in the visitor's own words, of things they expected to find and did
    not. The site has no search box today, so this table stays empty until one
    exists; the report is built and waiting.
    """

    QUERY_MAX_LENGTH = 200

    session = models.ForeignKey(
        Session, null=True, blank=True, on_delete=models.CASCADE, related_name='searches'
    )
    query = models.CharField(max_length=QUERY_MAX_LENGTH, db_index=True)
    normalized_query = models.CharField(
        max_length=QUERY_MAX_LENGTH,
        db_index=True,
        help_text='Lowercased and whitespace-collapsed, so the report groups '
                  '"Django" and "  django " as one query.',
    )
    result_count = models.PositiveIntegerField(default=0)
    clicked_result = models.BooleanField(default=False)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-occurred_at']
        verbose_name_plural = 'Search queries'
        indexes = [
            models.Index(fields=['result_count', '-occurred_at'], name='analytics_sq_zero'),
            models.Index(fields=['normalized_query'], name='analytics_sq_norm'),
        ]

    def __str__(self) -> str:
        return f'{self.query} ({self.result_count} results)'


class ExperimentAssignment(models.Model):
    """
    Which variant of an experiment a visitor saw.

    Assignment is computed by hashing ``visitor_id + experiment_key``, so it is
    stable without reading this table on every request. Rows exist to make the
    split auditable and to join results against, not to decide the variant.
    """

    KEY_MAX_LENGTH = 60
    VARIANT_MAX_LENGTH = 40

    visitor = models.ForeignKey(
        Visitor, on_delete=models.CASCADE, related_name='experiment_assignments'
    )
    experiment_key = models.CharField(max_length=KEY_MAX_LENGTH, db_index=True)
    variant = models.CharField(max_length=VARIANT_MAX_LENGTH)
    assigned_at = models.DateTimeField()

    class Meta:
        ordering = ['-assigned_at']
        unique_together = [('visitor', 'experiment_key')]
        indexes = [
            models.Index(fields=['experiment_key', 'variant'], name='analytics_exp_variant'),
        ]

    def __str__(self) -> str:
        return f'{self.experiment_key}={self.variant}'


class VisitorIP(models.Model):
    """
    One row per distinct IP address seen, with the address stored in the clear.

    **This is the only table in the app that holds a raw IP address**, and it
    exists because the site owner asked for the address listing their previous
    ``api.Visitor`` model provided. Everything else in this app stays
    hash-only: `Session` keeps `ip_hash` plus a truncated network and nothing
    else, and none of the reporting joins against this table.

    That isolation is the point. The privacy model documented in
    :mod:`analytics.privacy` still holds everywhere else, and turning the
    feature off is one setting plus one ``DROP TABLE`` — no other data is
    entangled with it.

    Aggregated rather than append-only, matching the model it replaces: one row
    per address with a running count, so the table is bounded by the number of
    distinct visitors rather than growing with every request.

    Gated on ``ANALYTICS['STORE_RAW_IPS']`` and purged on its own retention
    clock, ``ANALYTICS['IP_RETENTION_DAYS']``.
    """

    PATH_MAX_LENGTH = 200
    USER_AGENT_MAX_LENGTH = 300

    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    is_public = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether the address is routable on the public internet. '
                  'Loopback and private ranges say nothing about where a '
                  'visitor came from.',
    )
    visit_count = models.PositiveIntegerField(default=0)
    first_seen_at = models.DateTimeField(db_index=True)
    last_seen_at = models.DateTimeField(db_index=True)
    last_path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    last_user_agent = models.CharField(max_length=USER_AGENT_MAX_LENGTH, blank=True)
    country = models.CharField(max_length=2, blank=True, db_index=True)
    is_bot = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-last_seen_at']
        verbose_name = 'Visitor IP address'
        verbose_name_plural = 'Visitor IP addresses'
        indexes = [
            models.Index(fields=['is_public', '-last_seen_at'], name='analytics_ip_public'),
            models.Index(fields=['is_bot', '-last_seen_at'], name='analytics_ip_bot'),
        ]

    def __str__(self) -> str:
        return self.ip_address


class DailyStat(models.Model):
    """
    Pre-aggregated daily counts, one row per dimension combination.

    The admin dashboard reads this table and nothing else, which is what keeps
    it fast as the raw tables grow. A null dimension means "all": the row with
    every dimension null is the site-wide total for that day.

    Rebuilt idempotently by the rollup job, so re-running a date range is
    always safe.
    """

    PATH_MAX_LENGTH = 200

    date = models.DateField(db_index=True)
    path = models.CharField(max_length=PATH_MAX_LENGTH, null=True, blank=True)
    country = models.CharField(max_length=2, null=True, blank=True)
    device_type = models.CharField(
        max_length=10, choices=DeviceType.choices, null=True, blank=True
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, null=True, blank=True)

    pageviews = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    sessions = models.PositiveIntegerField(default=0)
    bounces = models.PositiveIntegerField(default=0)
    total_engaged_seconds = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ['-date']
        # Postgres treats every NULL as distinct, so a plain unique_together
        # would not stop duplicate site-wide rows. The rollup therefore deletes
        # a date's rows before rewriting them, and this constraint catches any
        # non-null duplicate.
        unique_together = [('date', 'path', 'country', 'device_type', 'channel')]
        indexes = [
            models.Index(fields=['-date', 'path'], name='analytics_ds_date_path'),
            models.Index(fields=['-date', 'country'], name='analytics_ds_country'),
            models.Index(fields=['-date', 'channel'], name='analytics_ds_channel'),
        ]

    def __str__(self) -> str:
        dimensions = [d for d in (self.path, self.country, self.device_type, self.channel) if d]
        label = ' · '.join(dimensions) if dimensions else 'site-wide'
        return f'{self.date} {label}'
