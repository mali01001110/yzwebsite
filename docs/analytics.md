# Visitor analytics

First-party visitor analytics for yzwebsite. All data stays in this project's
own Postgres database and is read through the existing Django admin. No Google
Analytics, no third-party script, no external service, and **no new
dependencies** — Python or npm.

- [Setup](#setup)
- [How it works](#how-it-works)
- [Settings reference](#settings-reference)
- [Event taxonomy](#event-taxonomy)
- [Privacy model](#privacy-model) — including the [raw IP listing](#raw-ip-listing) exception
- [Operations](#operations)
- [Removing the app](#removing-the-app)

---

## Setup

The app is already installed. Nothing further is required for it to collect
data — these are the optional pieces.

### 1. Confirm it is wired in

`analytics` is in `INSTALLED_APPS`, two middleware entries are at the end of
`MIDDLEWARE`, and `api/urls.py` mounts `analytics.urls` under
`/api/analytics/`. Verify with:

```bash
python manage.py check
python manage.py test analytics
```

### 2. Look at the dashboard

Django admin → **Analytics** → **Daily stats** → the `dashboard/` URL, or go
straight to `<admin>/analytics/dailystat/dashboard/`, where `<admin>` is the
path set by `DJANGO_ADMIN_URL` (`/dev-admin/` in local development).

### 3. Optional: MaxMind GeoLite2

Country already works for free through Cloudflare's `CF-IPCountry` header.
MaxMind adds city, coordinates, timezone and ASN — and the ASN data is what
powers the datacenter bot signal.

```bash
export MAXMIND_LICENSE_KEY=...          # free account at maxmind.com
python manage.py update_geoip
python manage.py update_geoip --status  # verify
```

Then in settings:

```python
ANALYTICS = {
    'GEOIP_ENABLED': True,
    'GEOIP_PATH': BASE_DIR / 'geoip',
}
```

Render's filesystem is ephemeral, so on production this belongs in `build.sh`,
not run once by hand. The two databases total roughly 70 MB per deploy.

### 4. Optional: consent gating

Off by default. To turn it on, set `ANALYTICS['REQUIRE_CONSENT'] = True` **and**
change `<ConsentBanner enabled={false} />` to `enabled` in
`frontend/src/App.jsx`. Both, together — a banner shown while the server is not
gating asks a question whose answer changes nothing.

---

## How it works

```
request → CollectorMiddleware → in-process buffer → daemon thread → Postgres
                (< 1 ms)          (deque)          (flush + jobs)      ↓
browser → beacon.js → /api/analytics/events/ → buffer ──┘          DailyStat
                                                                        ↓
                                                                 admin dashboard
```

**Nothing writes to the database during a request.** The middleware builds a
dict of primitives and appends it to an in-process buffer. A single daemon
thread drains it every 5 seconds or 500 rows, does the enrichment (geo, ASN,
user-agent parsing, bot scoring) and writes in bulk.

The same thread runs the periodic jobs — sessionization every 5 minutes, rollup
hourly, retention daily — each guarded by a Postgres advisory lock so a second
process cannot double-run one. Every job is idempotent.

There is no Redis and no Celery. See
[`adr/0001-first-party-analytics-pipeline.md`](adr/0001-first-party-analytics-pipeline.md)
for why, and for when to revisit that.

### Sections are pages

This site is a single route with anchored sections. A section scrolling into
view is recorded as a `PageView` with `path='/#skills'` and
`is_spa_navigation=True`, so section reporting reuses the path index, the
`DailyStat.path` dimension and the engagement fields rather than needing a
parallel model. "Top pages" therefore reads as "top sections", which is the
question this site actually has an answer to.

### Modules

| Module | Responsibility |
| --- | --- |
| `middleware.py` | Tier 1 collection and consent resolution. Buffer-only. |
| `client_ip.py` | Address resolution. Moved from `api/`, plus `CF-Connecting-IP`. |
| `privacy.py` | Hashing, truncation, scrubbing. Every other module goes through it. |
| `buffer.py` | The bounded in-process write queue. |
| `pipeline.py` | Flush, enrichment, sessionization, rollup, retention, scheduler. |
| `useragent.py` | Client hints and a UA fallback parser. No dependency. |
| `geo.py` | `CF-IPCountry`, and optional MaxMind. Fails soft. |
| `channels.py` | Referrer host → acquisition channel. |
| `security.py` | Scan, enumeration and abuse detection. Records, never blocks. |
| `consent.py` | Consent categories, DNT and Sec-GPC. |
| `serializers.py` / `views.py` | The beacon ingest endpoint. |
| `events.py` | `track_event()`, site search, A/B assignment. |
| `reports.py` | Dashboard queries. Reads `DailyStat`, not the raw tables. |
| `admin.py` | Read-only admin plus the dashboard view. |
| `exports.py` | Data-subject export and erasure. |
| `defaults.py` | Every setting, with its default. |

---

## Settings reference

All settings live in one `ANALYTICS` dict. Only state what you want to change;
everything else falls back to `analytics/defaults.py`.

```python
ANALYTICS = {
    'REQUIRE_CONSENT': True,
}
```

### Collection

| Setting | Default | Meaning |
| --- | --- | --- |
| `ENABLED` | `True` | Master switch. Off makes the middleware a passthrough. |
| `TRUSTED_IP_HEADERS` | `['HTTP_CF_CONNECTING_IP']` | Proxy-set headers tried before `X-Forwarded-For`. **Only safe while every route to the origin passes through that proxy.** |
| `EXCLUDE_PATH_PREFIXES` | `/admin/ /api/ /static/ /assets/ /media/` | Overridden in `settings.py`, which derives it from `BACKEND_URL_PREFIXES` so the path set by `DJANGO_ADMIN_URL` is excluded in place of `/admin/`. |
| `EXCLUDE_PATHS` | favicon, icons, background, robots, sitemap | Root-level files WhiteNoise serves from `frontend/dist`. |

`TRUSTED_PROXY_COUNT` is deliberately **not** in this dict. It is a root-level
setting, read by `client_ip.py`, asserted by 11 tests, and wired to
`DJANGO_TRUSTED_PROXY_COUNT` in `render.yaml` (currently `2`, for
Cloudflare → Render → Django).

### Buffer and scheduler

| Setting | Default | Meaning |
| --- | --- | --- |
| `BUFFER_MAX_ROWS` | `500` | Flush once this many records are queued. |
| `FLUSH_INTERVAL_SECONDS` | `5` | Flush at least this often. |
| `BUFFER_HARD_LIMIT` | `50000` | Beyond this the buffer discards oldest and logs loudly. |
| `RUN_INLINE_SCHEDULER` | `True` | `False` moves all jobs to `run_analytics_jobs`. |
| `SESSIONIZE_INTERVAL_SECONDS` | `300` | |
| `ROLLUP_INTERVAL_SECONDS` | `3600` | |
| `RETENTION_INTERVAL_SECONDS` | `86400` | |
| `SESSION_TIMEOUT_MINUTES` | `30` | Idle time before a session closes. |

### Retention

| Setting | Default | Meaning |
| --- | --- | --- |
| `RAW_RETENTION_DAYS` | `90` | Then raw pageviews, events, security events and searches are deleted. |
| `LOCATION_RETENTION_DAYS` | `30` | Then `ip_truncated`, coordinates, city and region are nulled. |
| `PURGE_BATCH_SIZE` | `5000` | Deletion batch size. |

`DailyStat` rollups are **never** deleted.

### Privacy

| Setting | Default | Meaning |
| --- | --- | --- |
| `SALT_ROTATION_HOURS` | `24` | How often the visitor identifier changes. |
| `QUERY_PARAM_ALLOWLIST` | utm_*, click ids, `ref`, `page`, `q` | Everything else is hashed, never stored. |
| `REQUIRE_CONSENT` | `False` | Gate Tier 2 on the consent cookie. |
| `CONSENT_COOKIE_NAME` | `analytics.consent` | |
| `HONOR_DNT` | `True` | `DNT: 1` / `Sec-GPC: 1` are a hard Tier 2 opt-out. |

### Raw IP listing

| Setting | Default | Meaning |
| --- | --- | --- |
| `STORE_RAW_IPS` | `True` | Populate `VisitorIP`. **The only place an address is stored in the clear.** |
| `STORE_PRIVATE_IPS` | `True` | Also record loopback and private ranges, flagged `is_public=False`. |
| `IP_RETENTION_DAYS` | `90` | Then the address row is deleted, on its own clock. |

### Ingest

| Setting | Default |
| --- | --- |
| `INGEST_MAX_BATCH_SIZE` | `50` |
| `INGEST_MAX_BODY_BYTES` | `65536` |
| `INGEST_MAX_PROP_BYTES` | `4096` |
| `INGEST_THROTTLE_RATE` | `120/hour` |
| `EVENT_ALLOWLIST` | see below |
| `SECTION_ALLOWLIST` | the ten ids from `frontend/src/data/navigation.js` |

### Geo, security, dashboard

| Setting | Default | Meaning |
| --- | --- | --- |
| `COUNTRY_HEADER` | `HTTP_CF_IPCOUNTRY` | Free country data from Cloudflare. |
| `GEOIP_ENABLED` | `False` | MaxMind. Needs the `geoip2` package. |
| `GEOIP_PATH` | `None` | Directory holding the `.mmdb` files. |
| `SCAN_PATTERNS` | ~30 markers | CMS, config, VCS and DB-admin probe paths. |
| `ENUMERATION_WINDOW_SECONDS` | `300` | |
| `ENUMERATION_THRESHOLD` | `15` | Rejected detail requests in the window. |
| `SCAN_REPEAT_THRESHOLD` | `5` | Above this an address is a repeat offender. |
| `DASHBOARD_DEFAULT_DAYS` | `30` | |
| `LIVE_WINDOW_MINUTES` | `5` | The "active now" window. |
| `PAGINATOR_COUNT_LIMIT` | `10000` | Above this the admin estimates row counts. |
| `PARTITION_PAGEVIEWS` | `False` | Monthly partitioning. Not built; see the plan doc. |

---

## Event taxonomy

Only names on `EVENT_ALLOWLIST` are accepted. Anything else is rejected at
ingest, so a fuzzed client cannot grow the `name` column's cardinality.

### Recorded as `PageView` rows

| Name | Emitted when | Notable props |
| --- | --- | --- |
| `pageview` | Page load, or a router navigation | `path`, `title` |
| `section_view` | A section scrolls 50% into view | `path='/#<section>'` |

### Recorded as `Event` rows

| Name | Emitted when | Notable props |
| --- | --- | --- |
| `scroll_depth` | 25 / 50 / 75 / 100% first reached | `depth` |
| `engagement` | Page hide or route change | `engaged_seconds`, `max_scroll_depth` |
| `outbound_click` | A link to another host | `host`, `href` |
| `file_download` | A link to a document or media file | `file` |
| `rage_click` | 3+ clicks within 40px in 1s | `count`, `target` |
| `dead_click` | Click on a non-interactive element, no DOM change in 500ms | `target` |
| `form_start` | First focus inside an opted-in form | `form` |
| `form_abandon` | Page hidden with a form started but not submitted | `form`, `last_field` |
| `form_submit` | An opted-in form submits | `form` |
| `js_error` | `window.onerror` or `unhandledrejection` | `message`, `source`, `line`, `stack` |
| `web_vital` | On page hide | `metric` (LCP/INP/CLS/TTFB/FCP), value in `value` |
| `site_search` / `search_result_click` | Reserved — no search box exists yet | |
| `signup` / `login` / `logout` | Auth signals | |
| `contact_submitted` | The contact form is accepted server-side | |
| `experiment_view` | An experiment variant is shown | |

**Form tracking is opt-in and never reads values.** Add
`data-analytics-form="contact"` to a `<form>`; only the form name and the last
focused field's *name* are recorded.

### Emitting events

From the browser:

```js
const { track, trackPageview, identify } = useAnalytics();
track('outbound_click', { host: 'example.com' });
```

From Django:

```python
from analytics.events import track_event

track_event(request, 'contact_submitted')
track_event(request, 'form_submit', props={'form': 'contact'}, value=None)
```

`track_event` never raises, never writes synchronously, and returns `False` for
an unregistered name.

### A/B tests

```python
from analytics.events import assign_variant

variant = assign_variant(visitor_id, 'hero-copy', ('control', 'treatment'))
```

Assignment is a hash of `visitor_id + experiment_key` — stable across requests
and processes with no database read. `ExperimentAssignment` rows exist to audit
the split, not to decide it.

---

## Privacy model

Four rules, enforced in `analytics/privacy.py` so nothing else reimplements them.

### 1. No raw IP address is stored, except in one isolated table

Every table but one holds only:

- `ip_hash` — `HMAC-SHA256(daily_salt, ip)`, truncated to 64 chars
- `ip_truncated` — IPv4 with the last octet zeroed (`93.184.216.0`), IPv6 with
  the last 80 bits zeroed (`2001:db8:1234::`)

**The exception is `VisitorIP`**, which stores the address in the clear because
the site owner asked for the address listing back. It is gated on
`ANALYTICS['STORE_RAW_IPS']` and covered in
[Raw IP listing](#raw-ip-listing) below.

The isolation is deliberate and is asserted by tests: `Session`, `PageView`,
`Event` and `SecurityEvent` are unaffected by that setting, no report or
dashboard query joins against `VisitorIP`, and nothing derives a hash from it.
Turning the feature off and dropping one table restores the original position
with no other data touched.

### 2. The visitor identifier rotates every 24 hours

```
visitor_id = HMAC-SHA256(daily_salt, ip + "|" + user_agent)[:64]
```

The salt is *derived*, not stored: `sha256(SECRET_KEY + period_number)`. There
is no salt table to leak, every process derives the same value with no
coordination, and old salts simply cease to be derivable.

This buys stable daily unique counts with no cookie. The deliberate cost:

- The same person on two consecutive days is two visitors. The dashboard says
  **"visitor-days"**, not "unique visitors", because summing daily uniques over
  a month is not a monthly unique count and labelling it as one would be a lie.
- Rotating `SECRET_KEY` rotates every identifier. That is correct behaviour.

HMAC rather than a plain `sha256(salt + data)`: the IPv4 space is 2^32, small
enough to brute-force, and HMAC is the right construction for keyed hashing.

### 3. Query strings are never stored verbatim

Allowlisted parameters (utm_*, click ids, `ref`, `page`, `q`) are kept in the
clear. Everything else is folded into an opaque `query_hash`, so a
password-reset token pasted into a URL never reaches the database. Referrer
query strings are dropped entirely — they belong to somebody else's site.

### 4. Free text is scrubbed before storage

Emails, JWTs, bearer/api-key/password assignments, long opaque strings and
anything IPv4-shaped are replaced in JS error messages, stack traces and string
event properties. Deliberately over-broad: a false positive costs a redacted
debug string, a false negative writes a credential to the database.

### Consent

| Category | Gated? |
| --- | --- |
| **essential** — path, status, timing, truncated IP | Never. Needed to operate and defend the site. |
| **analytics** — everything from the beacon | On `REQUIRE_CONSENT` (currently `False`). |

`DNT: 1` and `Sec-GPC: 1` are honoured as a hard Tier 2 opt-out **regardless of
`REQUIRE_CONSENT` and regardless of cookie state**. They are browser signals,
not any one jurisdiction's rule, and someone who set one has already answered.

### Raw IP listing

Django admin → **Analytics** → **Visitor IP addresses**.

One row per address seen, with a running visit count — the same shape as the
`api.Visitor` model this replaced, plus country and a bot flag. Public
addresses show by default; loopback and private ranges are recorded but
filtered out of the default view, since they say nothing about where a visitor
came from.

**This is a deliberate exception to the privacy model, and it is worth being
clear-eyed about it.** A raw IP address is personal data in most jurisdictions.
Everything else in this app was built specifically to avoid holding one. This
table holds them because the feature was asked for.

What limits the exposure:

- **One table.** Nothing else stores an address, nothing joins against it, and
  no report reads it. The isolation is asserted by tests.
- **Bounded size.** One row per address, not one per request.
- **Its own retention clock.** `IP_RETENTION_DAYS` (90) deletes rows outright
  rather than blanking them — a row with no address in it is worth nothing.
- **One switch and one table to remove it**, below.

Note the asymmetry this creates: `VisitorIP` is searchable by address, so an
erasure request naming an IP can actually be answered here — which the hashed
side cannot do once the salt has rotated.

**To turn it off:**

```python
ANALYTICS = {'STORE_RAW_IPS': False}      # stops new rows immediately
```

```sql
-- then, to remove what was already collected:
DROP TABLE analytics_visitorip;
```

Nothing else in the app reads that table, so dropping it breaks nothing. Remove
the model and its admin registration too if you want `makemigrations` to stay
quiet.

### Data-subject requests

```bash
python manage.py visitor_data --export <visitor_id>
python manage.py visitor_data --export <visitor_id> --output subject.json
python manage.py visitor_data --delete <visitor_id> --yes

# By address — only reaches the VisitorIP listing, but it is the form a real
# request usually arrives in, since nobody knows their own visitor hash.
python manage.py visitor_data --export-ip 93.184.216.34
python manage.py visitor_data --delete-ip 93.184.216.34 --yes
```

Or in code: `analytics.exports.export_visitor_data(visitor_id)` /
`delete_visitor_data(visitor_id)` / `export_ip_data(ip)` / `delete_ip_data(ip)`.

`delete_ip_data` removes the address row only. Session and pageview rows are
left alone deliberately: they carry no address, so they identify nobody once
that row is gone, and deleting them would silently corrupt the historical
counts in `DailyStat`.

**A limitation worth stating to anyone who asks:** because the salt rotates,
these reach only the rows recorded under the identifier supplied. Earlier
activity carries a different identifier and is already unlinkable from any
individual — which is a stronger privacy position than being able to produce it
on demand, but it does mean a request cannot return "everything, ever".

Erasure cascades through sessions, pageviews, events, searches and experiment
assignments. `DailyStat` is untouched: it holds only counts, attributable to
nobody.

---

## Operations

### Management commands

| Command | Purpose |
| --- | --- |
| `rebuild_stats --start Y-M-D --end Y-M-D` | Rebuild the rollup. Idempotent. |
| `rebuild_stats --days 30` | Same, relative to today. |
| `run_analytics_jobs [--flush --sessionize --rollup --retention]` | Run jobs once, from outside the web process. |
| `update_geoip [--status]` | Download or check the MaxMind databases. |
| `seed_analytics --pageviews N --yes` | Generate synthetic data. Never on production. |
| `seed_analytics --benchmark` | Time every dashboard query against the 500 ms budget. |
| `visitor_data --export / --delete` | Data-subject requests, by visitor hash. |
| `visitor_data --export-ip / --delete-ip` | Data-subject requests, by IP address. |
| `partition_pageviews --status` | Inspect PageView partitioning. |
| `partition_pageviews --convert --yes` | One-time conversion to monthly partitions. |

### Partitioning PageView

Built, Postgres-only, and **off**. `ANALYTICS['PARTITION_PAGEVIEWS']` defaults
to `False` and no migration touches the table — conversion rewrites every row
in the largest table in the schema, so it belongs behind an explicit command
run against a quiesced, freshly backed-up database, not behind a deploy.

```bash
# 1. Set ANALYTICS['PARTITION_PAGEVIEWS'] = True
# 2. Stop write traffic, back up the database
python manage.py partition_pageviews --convert --yes
python manage.py partition_pageviews --status     # verify row counts
python manage.py partition_pageviews --drop-legacy --yes
```

What conversion does, and why in this order, is documented step by step in
`analytics/partitioning.py`. The one surprise: the primary key becomes
`(id, occurred_at)`, because Postgres requires the partition key in every
unique constraint. Django's ORM is unaffected.

Once converted, the scheduler calls `ensure_partitions()` on the daily
retention tick, so a month boundary never arrives without a partition ready.

**When this is worth doing:** somewhere north of 50 million rows. At ~500
pageviews/day that is decades away. It ships off for that reason.

### Moving the jobs out of the web process

Set `ANALYTICS['RUN_INLINE_SCHEDULER'] = False` and schedule:

```
*/5  * * * *   python manage.py run_analytics_jobs --flush --sessionize
17   * * * *   python manage.py run_analytics_jobs --rollup
40   3 * * *   python manage.py run_analytics_jobs --retention
```

No code changes. Do this when you add a second web instance, or when losing a
flush window on restart stops being acceptable.

### What to watch in the logs

| Message | Meaning |
| --- | --- |
| `Analytics buffer overflowed` | The flush thread is behind, or the database is down. Rows were discarded. |
| `Analytics flush failed` | A whole batch was lost. The transaction rolled back cleanly. |
| `GeoIP database missing` | `GEOIP_ENABLED` is on but the `.mmdb` is absent. Country still resolves. |
| `Rejected analytics event with unregistered name` | A caller used a name not on the allowlist. |

### Performance

- The dashboard reads `DailyStat` only, so its cost is flat as the raw tables
  grow. `assertNumQueries` tests in `analytics/tests.py` pin the query counts.
- The admin changelists use `EstimatedCountPaginator`, which replaces
  `COUNT(*)` with the Postgres planner's `reltuples` estimate above 10,000
  rows. Filtered views still count exactly.
- BRIN indexes on the append-only timestamps and a GIN index on `Event.props`
  are created by `analytics/migrations/0002_postgres_indexes.py`, **behind a
  vendor check** — they are skipped on SQLite so the suite runs anywhere.

---

## Removing the app

The feature is designed to come out in one piece:

1. Delete the `analytics/` directory.
2. Remove `'analytics'` from `INSTALLED_APPS`.
3. Remove the two `analytics.middleware.*` entries from `MIDDLEWARE`.
4. Remove the `path('analytics/', include('analytics.urls'))` line from
   `api/urls.py`.
5. Remove the `track_event` import and its one call in `api/views.py`.
6. Remove `useAnalytics` and `ConsentBanner` from `frontend/src/App.jsx`, and
   delete `frontend/src/hooks/useAnalytics.js` and
   `frontend/src/components/ConsentBanner.jsx`.
7. Drop the `analytics_*` tables — including `analytics_visitorip`, which is
   the only one holding raw addresses.

Those seven points are the app's entire footprint outside its own directory.
Nothing else in the project imports from it, and it imports nothing from `api`.
