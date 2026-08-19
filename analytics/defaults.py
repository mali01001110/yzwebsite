"""
Every setting the analytics app understands, with its default.

The app is configured through a single ``ANALYTICS`` dict in project settings.
Anything absent from that dict falls back to ``DEFAULTS`` below, so a project
only ever states what it wants to change.

Two settings deliberately live outside this dict because the project already
owns them: ``TRUSTED_PROXY_COUNT`` (read by :mod:`analytics.client_ip`, wired to
``DJANGO_TRUSTED_PROXY_COUNT`` in render.yaml) and ``CORS_ALLOWED_ORIGINS`` /
``ALLOWED_HOSTS`` (read by the ingest endpoint's origin check).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver

SETTINGS_KEY = 'ANALYTICS'

DEFAULTS: dict[str, Any] = {
    # -- master switch ------------------------------------------------------
    # Turns off collection entirely. The middleware stays installed and becomes
    # a passthrough, so toggling this needs no deploy-time settings surgery.
    'ENABLED': True,

    # -- client IP resolution ----------------------------------------------
    # Headers tried, in order, before falling back to X-Forwarded-For. These are
    # only trustworthy because the named proxy overwrites them on every request;
    # adding a header a visitor can set would let them forge their own address.
    # Cloudflare proxies this domain, so CF-Connecting-IP is authoritative.
    'TRUSTED_IP_HEADERS': ['HTTP_CF_CONNECTING_IP'],

    # -- what not to collect ------------------------------------------------
    # Derived from BACKEND_PREFIXES in the root URLconf plus the files
    # WhiteNoise serves out of frontend/dist. Requests under these prefixes are
    # dropped before any work is done.
    'EXCLUDE_PATH_PREFIXES': [
        '/admin/',
        '/api/',
        '/static/',
        '/assets/',
        '/media/',
    ],
    # Exact paths, matched after prefixes. The compiled bundle's root-level
    # assets are files rather than directories, so they need naming outright.
    'EXCLUDE_PATHS': [
        '/favicon.ico',
        '/favicon.svg',
        '/icons.svg',
        '/site-background.jpg',
        '/robots.txt',
        '/sitemap.xml',
    ],

    # -- write buffer -------------------------------------------------------
    # The middleware appends to an in-process buffer and returns; a daemon
    # thread drains it. Flushing happens on whichever limit is reached first.
    'BUFFER_MAX_ROWS': 500,
    'FLUSH_INTERVAL_SECONDS': 5,
    # Beyond this the buffer discards its oldest entries rather than growing
    # without bound if the database is unreachable. Analytics must never be the
    # reason the site runs out of memory.
    'BUFFER_HARD_LIMIT': 50_000,

    # -- background scheduler ----------------------------------------------
    # One daemon thread owns the flush plus the periodic jobs. Set False to run
    # everything from management commands (Render Cron, GitHub Actions, cron)
    # instead. See docs/adr/0001-first-party-analytics-pipeline.md.
    'RUN_INLINE_SCHEDULER': True,
    'SESSIONIZE_INTERVAL_SECONDS': 300,
    'ROLLUP_INTERVAL_SECONDS': 3600,
    'RETENTION_INTERVAL_SECONDS': 86_400,

    # -- sessionization -----------------------------------------------------
    'SESSION_TIMEOUT_MINUTES': 30,

    # -- retention ----------------------------------------------------------
    # Raw rows are deleted after RAW_RETENTION_DAYS; DailyStat rollups are kept
    # indefinitely. Coordinates and the truncated IP are cleared sooner, since
    # their only purpose is short-window abuse investigation.
    'RAW_RETENTION_DAYS': 90,
    'LOCATION_RETENTION_DAYS': 30,
    'PURGE_BATCH_SIZE': 5_000,

    # -- raw IP listing -----------------------------------------------------
    # The one deliberate exception to "never store a raw IP". Populates the
    # VisitorIP table, which backs the address listing in the admin and is the
    # only place in this app an address is held in the clear. Everything else
    # stays hash-only whatever this is set to.
    #
    # Turning it off stops new rows immediately; dropping the existing table is
    # a separate step. See docs/analytics.md, "Raw IP listing".
    'STORE_RAW_IPS': True,
    # Record private and loopback addresses too, flagged is_public=False. On by
    # default so local development shows something; the admin filters on it.
    'STORE_PRIVATE_IPS': True,
    # Raw addresses expire on their own clock, independent of
    # RAW_RETENTION_DAYS, because they are the most sensitive thing stored and
    # the one most worth ageing out sooner if you choose to.
    'IP_RETENTION_DAYS': 90,

    # -- privacy ------------------------------------------------------------
    # visitor_id = sha256(daily_salt + ip + user_agent). The salt rotates every
    # 24h and old salts are discarded, which gives stable daily uniques with no
    # cookie and no raw IP at rest.
    'SALT_ROTATION_HOURS': 24,
    # Query parameters recorded in the clear. Everything else is folded into an
    # opaque query_hash, so a token accidentally placed in a URL is never
    # written to the database.
    'QUERY_PARAM_ALLOWLIST': [
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'gclid', 'fbclid', 'msclkid', 'ref', 'page', 'q',
    ],

    # -- consent ------------------------------------------------------------
    # Tier 1 (path, status, timing, truncated IP) is essential and always
    # collected. Tier 2 beacon data is gated on the analytics consent cookie
    # only when REQUIRE_CONSENT is on.
    'REQUIRE_CONSENT': False,
    'CONSENT_COOKIE_NAME': 'analytics.consent',
    'CONSENT_COOKIE_MAX_AGE': 60 * 60 * 24 * 180,
    # DNT and Sec-GPC are browser signals rather than any one jurisdiction's
    # law, so they are honoured as a hard Tier 2 opt-out regardless of consent.
    'HONOR_DNT': True,

    # -- geo enrichment -----------------------------------------------------
    # Cloudflare sends CF-IPCountry on every plan, which covers country for free
    # with no dependency and no database to ship. MaxMind adds city,
    # coordinates and ASN, and needs the `geoip2` package plus GEOIP_PATH.
    'COUNTRY_HEADER': 'HTTP_CF_IPCOUNTRY',
    'GEOIP_ENABLED': False,
    'GEOIP_PATH': None,
    'GEOIP_CITY_FILENAME': 'GeoLite2-City.mmdb',
    'GEOIP_ASN_FILENAME': 'GeoLite2-ASN.mmdb',

    # -- ingest endpoint ----------------------------------------------------
    'INGEST_MAX_BATCH_SIZE': 50,
    'INGEST_MAX_BODY_BYTES': 64 * 1024,
    'INGEST_MAX_PROP_BYTES': 4 * 1024,
    'INGEST_THROTTLE_RATE': '120/hour',
    # Event names the ingest endpoint will accept. Anything else is rejected,
    # so a compromised or fuzzed client cannot create unbounded name cardinality.
    'EVENT_ALLOWLIST': [
        'pageview', 'section_view', 'scroll_depth', 'engagement',
        'outbound_click', 'file_download', 'rage_click', 'dead_click',
        'form_start', 'form_abandon', 'form_submit',
        'js_error', 'web_vital', 'site_search', 'search_result_click',
        'signup', 'login', 'logout', 'contact_submitted', 'experiment_view',
    ],
    # Section anchors from frontend/src/data/navigation.js. Section views are
    # recorded as PageView rows with path='/#<id>', so this doubles as the path
    # allowlist for client-reported views.
    'SECTION_ALLOWLIST': [
        'home', 'about-me', 'skills', 'projects', 'education',
        'certifications', 'resume', 'cover-letter', 'social', 'contact',
    ],

    # -- bot detection ------------------------------------------------------
    'BOT_UA_KEYWORDS': [
        'bot', 'crawl', 'spider', 'slurp', 'scrape', 'curl', 'wget',
        'python-requests', 'httpclient', 'headless', 'phantomjs',
        'lighthouse', 'pingdom', 'uptimerobot', 'monitor', 'preview',
        'facebookexternalhit', 'embedly', 'quora link preview',
    ],

    # -- security signals ---------------------------------------------------
    # Substrings that only ever appear in scans for software this site does not
    # run. Matched case-insensitively against the path of any 404.
    'SCAN_PATTERNS': [
        'wp-admin', 'wp-login', 'wp-content', 'wp-includes', 'xmlrpc.php',
        '.env', '.git/', '.svn/', '.hg/', 'config.php', 'configuration.php',
        'phpmyadmin', 'pma/', 'adminer', 'mysql', 'dbadmin',
        '.aws/', '.ssh/', 'id_rsa', '.htpasswd', 'web.config',
        'vendor/phpunit', 'eval-stdin.php', 'shell.php', 'cgi-bin',
        'actuator/', 'solr/', 'jenkins', 'struts',
    ],
    # A burst of 404/403 on detail-style URLs from one address reads as ID
    # enumeration rather than a visitor who mistyped something.
    'ENUMERATION_WINDOW_SECONDS': 300,
    'ENUMERATION_THRESHOLD': 15,
    'SCAN_REPEAT_THRESHOLD': 5,

    # -- admin dashboard ----------------------------------------------------
    'DASHBOARD_DEFAULT_DAYS': 30,
    'LIVE_WINDOW_MINUTES': 5,
    'DASHBOARD_TOP_N': 10,
    # The raw tables are append-only and large; the admin changelist pager
    # estimates the row count instead of running COUNT(*) above this size.
    'PAGINATOR_COUNT_LIMIT': 10_000,

    # -- partitioning -------------------------------------------------------
    # Monthly declarative partitioning of PageView. Off until volume justifies
    # it; see section 5 of docs/analytics-plan.md for the migration path.
    'PARTITION_PAGEVIEWS': False,
    'PARTITION_AHEAD_MONTHS': 3,
}

_cache: dict[str, Any] | None = None


def get_settings() -> dict[str, Any]:
    """Return DEFAULTS merged with the project's ``ANALYTICS`` dict."""
    global _cache
    if _cache is None:
        _cache = {**DEFAULTS, **getattr(settings, SETTINGS_KEY, {})}
    return _cache


def get_setting(name: str) -> Any:
    """
    Return one analytics setting.

    Raises KeyError for an unknown name rather than returning None, so a typo
    in a setting name fails loudly instead of silently disabling a feature.
    """
    return get_settings()[name]


@receiver(setting_changed)
def _reset_cache(sender, setting, **kwargs) -> None:
    """Let ``override_settings`` change analytics configuration inside tests."""
    if setting == SETTINGS_KEY:
        global _cache
        _cache = None
