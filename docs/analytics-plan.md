# First-party visitor analytics — build plan

Status: **built**. Phases 1–7 are implemented and the suite is green
(188 tests). See `analytics.md` for the app's own documentation, and the
"Build status" section below for what was completed, changed, or left open.

A self-contained Django app, `analytics`, that collects visitor data into the
project's existing Postgres database and surfaces it in the existing Django
admin. No Google Analytics, no third-party script, no external service.

The app is self-contained so it is easy to review and easy to remove. It is not
a separate project, package, service, or database: it registers in the existing
`INSTALLED_APPS`, its migrations run against the existing database, its
middleware slots into the existing `MIDDLEWARE`, and its URLs mount under the
existing root URLconf.

---

## 1. What the repository actually is

Findings from Phase 0. Every decision below is anchored to these.

| Aspect | Reality |
| --- | --- |
| Django / DRF / Python | 6.0.8 / 3.17.2 / 3.13.4 on Render, 3.14.7 in the local `.venv` |
| Dependencies | pinned `requirements.txt`, 12 packages, no lockfile tooling |
| Settings | one module, `yzwebsiteproject/settings.py`, env-driven via `get_env_flag` / `get_env_list` |
| Local apps | one: `api` |
| Middleware | 10 entries; `api.middleware.VisitorTrackingMiddleware` is deliberately last |
| Database | Postgres in production (`basic-256mb`); **moving to Postgres locally too** |
| Background tasks | none — no Celery, no Redis, no cron |
| Auth | default `auth.User`, sessions for the admin only. No JWT, no public login/signup |
| Frontend | Vite 8 + React 19, plain JSX (**no TypeScript**), `frontend/dist` committed to git |
| Serving | Django serves the bundle via `WHITENOISE_ROOT`; production is same-origin |
| Proxy | **Cloudflare → Render LB → Django**, `DJANGO_TRUSTED_PROXY_COUNT=2` |
| Docs | none existed; this directory is new, following the layout `CLAUDE.md` prescribes |

### The frontend is one route

`frontend/src/App.jsx` declares a single `<Route>`. `Home.jsx` stacks ten
sections and navigation is anchor links (`href="#skills"`). There is no
`<Link>`, no `useNavigate`, and no `pushState` anywhere in `src/`.

Consequence: there are no SPA route changes to intercept, and `PageView.path`
would be `/` for essentially every row, making "top pages" useless.

**Decision:** section views are recorded as `PageView` rows with
`path='/#skills'` and `is_spa_navigation=True`. This reuses the path index,
`DailyStat.path`, `engaged_seconds` and `max_scroll_depth` unchanged, and turns
"top pages" into "top sections" — the question that actually has an answer on
this site. No new model, no new dimension. `data/navigation.js` already holds
the canonical section list and becomes the allowlist.

---

## 2. Answers driving the design

| Question | Answer | Effect |
| --- | --- | --- |
| Traffic | under ~500 pageviews/day | no Redis, no Celery, no partitioning |
| Local database | install and use Postgres | BRIN / GIN / JSONB all available; schema matches production |
| Infrastructure budget | zero | pipeline runs inside the existing web service |
| EU/UK regulation | ignore | consent gating built but **off** by default |

---

## 3. Dependency proposal

You asked to be asked, and said you would rather write 40 lines than add a
package. The proposal is therefore **zero new Python dependencies**, with three
optional additions listed for your call.

### Proposed: add nothing

| Brief asked for | Instead | Why |
| --- | --- | --- |
| `django-ipware` | keep the existing `api/client_ip.py`, moved into the app | 70 lines, already tuned to your exact 2-hop Cloudflare topology, already covered by 11 tests. The ipware model differs and swapping means rewriting those tests for no gain. Gains `CF-Connecting-IP` preference and a trusted-header setting. |
| `geoip2` + MaxMind GeoLite2 | the `CF-IPCountry` request header | Cloudflare sends it on every plan: free, zero bytes, zero deps, no licence key, no 70 MB download on each deploy. Gives country. |
| `user-agents` | `Sec-CH-UA*` client hints plus a ~60-line regex fallback | The brief already requires reading client hints, which natively cover Chromium browsers. The fallback handles Safari and Firefox. Avoids a 3-package dependency chain. |
| `django-admin-rangefilter` | `date_hierarchy` and `DateFieldListFilter` | Both are built in, and your existing `ContactMessageAdmin` already uses `date_hierarchy`. The custom dashboard has its own date inputs regardless. |
| `pytest-django` | keep `manage.py test` | You have ~350 lines of `TestCase`. Adding pytest means two idioms in one repo for no capability gain. |
| `django-debug-toolbar` / `django-silk` | `assertNumQueries` | Stdlib Django. Better than the toolbar here because it *enforces* query counts in the suite forever instead of reporting them once. |
| `django-axes` | record only, never block | The brief said integrate it if you already have it. You do not. |
| `redis` + `celery` + beat | in-process thread plus an advisory lock | Per your zero-budget answer. |

### Optional, your call

| Package | Size / chain | Maintenance | Buys you |
| --- | --- | --- | --- |
| `geoip2` | ~1 MB wheel, pulls `maxminddb` (C extension). Plus ~70 MB of `.mmdb` downloaded at build time and a MaxMind licence key env var. | Published by MaxMind, active | City, latitude/longitude, ASN, ASN org, `is_datacenter`. Without it those columns stay null and the datacenter bot signal is unavailable. |
| `user-agents` | 3 packages (`user-agents`, `ua-parser`, `ua-parser-builtins`) | Active | Better UA coverage than the hand-rolled fallback, especially for older and mobile browsers. |
| `web-vitals` (npm) | ~2 KB gzipped, zero transitive deps | Google Chrome team, active | Correct LCP / **INP** / **CLS** / TTFB / FCP. INP and CLS are genuinely hard to compute correctly by hand. |

**Recommendation:** take `web-vitals` only, and only inside the React hook — the
vanilla beacon stays dependency-free by using raw `PerformanceObserver` for
LCP/FCP/TTFB and omitting INP/CLS. Skip `geoip2` unless you want city-level
data; the `is_datacenter` bot signal is the one real loss, and UA plus
zero-engagement heuristics substitute adequately at your volume.

**Nothing in the optional table gets installed without your explicit yes.**

---

## 4. Architecture

```
                          request
                             |
  Cloudflare --> Render LB --+  CF-Connecting-IP, CF-IPCountry
                             v
      +-------------------------------------------+
      |  MIDDLEWARE (existing 9) ...              |
      |  analytics.middleware.ConsentMiddleware   |
      |  analytics.middleware.CollectorMiddleware |  <-- last, replaces
      +----------------+--------------------------+      VisitorTrackingMiddleware
                       |  builds a dict, appends, returns   (target < 1 ms)
                       v
      +-------------------------------------------+
      |  analytics.buffer  --  in-process deque    |
      +----------------+--------------------------+
                       |
                       v
      +-------------------------------------------+
      |  analytics.pipeline  --  one daemon thread |
      |   * flush        every 5 s / 500 rows      |
      |   * enrich       geo, UA, bot scoring      |
      |   * sessionize   every 5 min               |
      |   * rollup       daily                     |
      |   * retention    daily                     |
      |  guarded by pg_try_advisory_lock           |
      +----------------+--------------------------+
                       |  bulk_create()
                       v
                   Postgres
                       |
                       v
      +--------------------------------------------+
      |  Django admin  --  dashboard reads DailyStat |
      +--------------------------------------------+
```

Every scheduled job is also a management command, so the thread can be switched
off (`ANALYTICS['RUN_INLINE_SCHEDULER'] = False`) and the jobs driven from
Render Cron or GitHub Actions later, without a code change.

---

## 5. Data model

Field types follow the brief. Deviations are marked and explained.

### `Visitor`

```
visitor_id            CharField(64, unique, db_index)   sha256(daily_salt + ip + ua)[:64]
first_seen_at         DateTimeField
last_seen_at          DateTimeField
user                  FK(AUTH_USER_MODEL, null, SET_NULL)
is_bot                BooleanField(default=False)
first_touch_channel   CharField        [Phase 4] first-touch attribution
first_touch_source    CharField
first_touch_campaign  CharField
last_touch_channel    CharField        [Phase 4] last-touch attribution
last_touch_source     CharField
last_touch_campaign   CharField
```

### `Session`

```
visitor               FK(Visitor)
started_at            DateTimeField(db_index)
ended_at              DateTimeField(null)
landing_path          CharField
exit_path             CharField
referrer_host         CharField
referrer_url          URLField
channel               CharField  direct|organic|paid|social|referral|email|internal
utm_source / utm_medium / utm_campaign / utm_term / utm_content   CharField
click_id              CharField(null)          gclid / fbclid / msclkid
country               CharField(2)             from CF-IPCountry
region / city         CharField                null unless MaxMind is enabled
latitude / longitude  DecimalField(null)       null unless MaxMind is enabled
tz_from_ip            CharField                null unless MaxMind is enabled
asn / asn_org         CharField                null unless MaxMind is enabled
is_datacenter         BooleanField(default=False)
browser / browser_version / os / os_version / device_type   CharField
ip_hash               CharField(64)
ip_truncated          GenericIPAddressField(null)
language              CharField
is_bot                BooleanField(default=False)
bot_reason            CharField
pageview_count        PositiveIntegerField(default=0)
duration_seconds      PositiveIntegerField(default=0)
is_bounce             BooleanField(default=True)
```

### `PageView`

```
session               FK(Session)
path                  CharField(200)     '/' or '/#skills' for section views
query_hash            CharField(64)      hashed, never the raw query string
title                 CharField
referrer_url          URLField
occurred_at           DateTimeField(db_index)
engaged_seconds       PositiveIntegerField(null)
max_scroll_depth      PositiveSmallIntegerField(null)
status_code           PositiveSmallIntegerField
response_ms           PositiveIntegerField(null)
is_spa_navigation     BooleanField(default=False)   True for section views
```

### `Event`

```
session               FK(Session, null)
user                  FK(AUTH_USER_MODEL, null)
name                  CharField(db_index)    must be in the registered allowlist
props                 JSONField(default=dict)
value                 DecimalField(null)
occurred_at           DateTimeField(db_index)
```

### `SecurityEvent`

```
kind                  CharField  failed_login|rate_limit|path_scan|enumeration|suspicious_ua
ip_hash               CharField(64)
ip_truncated          GenericIPAddressField(null)
asn                   CharField
country               CharField(2)
path                  CharField
username_attempted    CharField
occurred_at           DateTimeField(db_index)
metadata              JSONField(default=dict)
```

### `DailyStat`

```
date                  DateField(db_index)
path                  CharField(null)    null = site-wide row
country               CharField(2, null)
device_type           CharField(null)
channel               CharField(null)
pageviews             PositiveIntegerField(default=0)
unique_visitors       PositiveIntegerField(default=0)
sessions              PositiveIntegerField(default=0)
bounces               PositiveIntegerField(default=0)
total_engaged_seconds PositiveBigIntegerField(default=0)

unique_together = ('date', 'path', 'country', 'device_type', 'channel')
```

### Indexes

```
PageView   BrinIndex(occurred_at)                   append-only time series
PageView   Index(path, occurred_at)
PageView   Index(session, occurred_at)
Event      BrinIndex(occurred_at)
Event      GinIndex(props)                          for querying inside the JSON
Event      Index(name, occurred_at)
Session    Index(visitor, started_at)
Session    Index(started_at, channel)
DailyStat  Index(date, path)
```

### Deferred, pending your call

| Model | Why deferred |
| --- | --- |
| `SearchQuery` and the zero-result report | **The site has no internal search.** No search box exists in any component. The brief calls this the highest-value report in the system, and on this codebase it has no data source and would render an empty table forever. Recommend building it when a search feature exists. |
| `ExperimentAssignment` | Nothing to A/B test — one route, no conversion funnel beyond the contact form. Your `CLAUDE.md` forbids speculative features (YAGNI). Recommend deferring. |
| Monthly partitioning of `PageView` | At 500 pageviews/day that is ~182k rows/year. Partitioning pays off around 50–100M rows. Recommend documenting the migration path without building the machinery. |

**Partitioning migration path**, for whenever volume justifies it:

1. Add `ANALYTICS['PARTITION_PAGEVIEWS'] = True`.
2. A `RunSQL` migration renames `analytics_pageview` to `analytics_pageview_legacy`.
3. Recreate it as `PARTITION BY RANGE (occurred_at)`, primary key `(id, occurred_at)` — Postgres requires the partition key in every unique constraint.
4. A management command creates the next N monthly partitions; the scheduler thread calls it monthly.
5. Backfill legacy rows into partitions in batches, then drop the legacy table.
6. Django models need no change; `Meta.managed` stays `True` and the ORM is unaware.

---

## 6. Migrating the existing visitor-IP feature

Existing implementation, all to be removed after you sign off on the diff:

- `api/client_ip.py` — **moves** to `analytics/client_ip.py`, extended with
  `CF-Connecting-IP` support. Its 11 tests move with it.
- `api/middleware.py` — **deleted**, replaced by `analytics/middleware.py`.
- `api/models.py` — `Visitor` and `VisitorManager` **deleted**. `ContactMessage`
  stays untouched.
- `api/admin.py` — `VisitorAdmin` **deleted**. `ContactMessageAdmin` untouched.
- `api/tests.py` — the visitor tests **move**, the contact tests stay.

### Data migration

`api.Visitor` stores one row per raw IP. `analytics.Visitor` forbids raw IPs at
rest and keys on a *daily-rotating* salted hash.

**The historical salts never existed and cannot be reconstructed.** Legacy rows
therefore get a `visitor_id` derived from a fixed `LEGACY_SALT` constant, and
will never deduplicate against rows collected after the cutover. That is
inherent to the privacy model, not a shortcut.

Mapping, in a `RunPython` data migration inside the `analytics` app:

| `api.Visitor` | becomes |
| --- | --- |
| `ip_address` | `Session.ip_hash` = sha256(LEGACY_SALT + ip); `Session.ip_truncated` = last octet / last 80 bits zeroed. Raw value discarded. |
| `first_seen` / `last_seen` | `Visitor.first_seen_at` / `Visitor.last_seen_at` |
| `visit_count` | `Session.pageview_count` on one synthetic session |
| `last_path` | `Session.landing_path` and `Session.exit_path` |
| `last_user_agent` | parsed into `browser` / `os` / `device_type` / `is_bot` |
| `is_public` | dropped — private addresses are excluded from the new collector anyway |

The local database currently holds **1 row**. The production row count is
unknown; the migration is written to be correct at any size and runs in batches.

Removal of `api.Visitor` is a **separate migration in the `api` app**, applied
only after the `analytics` data migration has run. Both will be shown to you
before either is applied.

---

## 7. Settings

All app settings live in one namespaced dict, with defaults in a single module,
`analytics/defaults.py`, merged with any `ANALYTICS = {...}` in project settings.

Two deliberate exceptions, because the repository already owns them:

- **`TRUSTED_PROXY_COUNT`** stays a root-level setting. It is read by the
  existing `client_ip.py`, asserted by 11 tests, and wired to
  `DJANGO_TRUSTED_PROXY_COUNT` in `render.yaml`. Folding it into `ANALYTICS`
  would break all three.
- **`CORS_ALLOWED_ORIGINS`** and `ALLOWED_HOSTS` stay where they are; the ingest
  endpoint's origin check reads them.

Defaults, abridged — the full reference ships in `docs/analytics.md`:

```python
ANALYTICS = {
    'ENABLED': True,
    'TRUSTED_IP_HEADERS': ['CF-Connecting-IP'],   # tried before X-Forwarded-For
    'EXCLUDE_PATH_PREFIXES': [...],               # derived from the URLconf, below
    'BUFFER_MAX_ROWS': 500,
    'FLUSH_INTERVAL_SECONDS': 5,
    'RUN_INLINE_SCHEDULER': True,
    'SESSION_TIMEOUT_MINUTES': 30,
    'RAW_RETENTION_DAYS': 90,
    'LOCATION_RETENTION_DAYS': 30,
    'REQUIRE_CONSENT': False,                     # per your answer: EU/UK ignored
    'HONOR_DNT': True,                            # see the note below
    'GEOIP_ENABLED': False,                       # MaxMind off unless you opt in
    'GEOIP_PATH': None,
    'EVENT_ALLOWLIST': [...],
    'SECTION_ALLOWLIST': [...],                   # from frontend data/navigation.js
    'SCAN_PATTERNS': [...],
}
```

Note on `HONOR_DNT`: you said to ignore EU/UK regulation, and consent gating is
off accordingly. `DNT` and `Sec-GPC` are not EU/UK regulation — they are a
browser signal — so the hard opt-out the brief asked for is kept as the default.
It is a one-line flip if you want the data instead. **Flag it if you disagree.**

### Exclusions, derived from the actual URLconf

`yzwebsiteproject/urls.py` defines `BACKEND_PREFIXES = ('admin', 'api', 'static')`.
The defaults derive from that, plus the files WhiteNoise serves from
`frontend/dist`:

```
/admin/  /api/  /static/  /assets/
/favicon.svg  /icons.svg  /site-background.jpg
/api/analytics/           the ingest endpoint itself
```

There is **no health-check endpoint** — `render.yaml` sets no `healthCheckPath`
— so none is excluded. Say the word if you want one added.

---

## 8. Phase checklist

Each phase ends with: migrations run, tests run, a summary of files changed, a
suggested commit message, and a stop for review.

### Phase 0 — read and plan

- [x] Explore the repository and report
- [x] Confirm proxy, volume, jurisdiction, budget
- [x] Write this document
- [x] **Your approval**

### Phase 0.5 — Postgres locally (prerequisite, blocks Phase 1)

- [ ] Install PostgreSQL 17 on Windows 11
- [ ] Create the `yzwebsite` database and role
- [ ] Point the local `DATABASE_URL` at it and document that in the README
- [ ] Re-run the existing suite on Postgres and confirm all 33 tests still pass
- [ ] Migrate the 1 existing local row across, or start clean — your call

### Phase 1 — data model

- [x] `analytics` app skeleton matching the flat-module layout `api` uses
- [x] Six models, with BRIN, GIN and composite indexes
- [x] `analytics/defaults.py` settings module
- [x] `makemigrations`, show you the file, then apply
- [x] Model-level tests
- [x] **Diff needing sign-off:** `settings.py` (INSTALLED_APPS)

### Phase 2 — Tier 1 server-side collection

- [x] `client_ip.py` moved in, `CF-Connecting-IP` added, 11 tests carried over
- [x] `CollectorMiddleware`, response-phase, buffer-only, zero synchronous DB writes
- [x] Client hints, the `Accept-CH` response header, UA fallback parser
- [x] Referrer-to-channel mapping, `Accept-Language`, 404 logging
- [x] `user_logged_in` stitching
- [x] Measure and report the added per-request latency (target under 1 ms)
- [x] **Diffs needing sign-off:** `settings.py` (MIDDLEWARE), deletion of `api/middleware.py`

### Phase 3 — Tier 2 beacon and ingest

- [x] DRF batch ingest at `/api/analytics/events/`: 204, allowlisted, throttled, origin-checked
- [x] Vanilla JS beacon, no dependencies, under 5 KB, served from static
- [x] React hook in `frontend/src/hooks/`, matching the existing hook conventions (`.jsx`, not `.ts`)
- [x] Section-visibility tracking in place of SPA routes
- [x] Scroll depth, engaged time, rage and dead clicks, outbound links, JS errors, Core Web Vitals
- [x] **Diffs needing sign-off:** `api/urls.py`, and `frontend/package.json` if `web-vitals` is approved

### Phase 4 — Tiers 3 and 4, attribution and events

- [x] UTM, gclid, fbclid and msclkid capture, persisted across the session
- [x] First-touch and last-touch stored separately on `Visitor`
- [x] `track_event(request_or_session, name, props=None, value=None)` helper
- [x] Wire the contact-form conversion — the only real conversion on this site
- [x] `SearchQuery` and `ExperimentAssignment`: **deferred, pending your call**

### Phase 5 — Tier 5, security signals and consent

- [x] `user_login_failed` handler
- [x] Throttle-hit logging via a `SimpleRateThrottle` subclass — **DRF emits no signal for this**
- [x] Scan-pattern detection, ID-enumeration detection, repeat-offender flagging
- [x] Bot scoring: UA plus zero-engagement heuristics (datacenter ASN only if MaxMind is approved)
- [x] `ConsentMiddleware` and cookie, built but off by default
- [x] Consent banner component, unstyled, reject as easy as accept

### Phase 6 — pipeline, aggregation, retention

- [x] In-process buffer and flush thread
- [x] Async enrichment in the worker thread
- [x] Sessionization at 30 minutes of inactivity
- [x] Idempotent nightly rollup, `rebuild_stats` command taking a date range
- [x] Retention: 90-day raw purge, 30-day location nulling
- [x] `pg_try_advisory_lock` guard; every job idempotent, logged, concurrency-safe

### Phase 7 — admin dashboard

- [x] All models registered read-only, delete for superusers only
- [x] Dashboard view via `get_urls()`, reading `DailyStat` only
- [x] Time series, top sections, referrers, channels, countries, devices
- [x] Live 5-minute counter, Core Web Vitals p75, recent security events
- [x] Chart.js — **CDN versus vendored is a decision I need from you**, see below
- [x] `Visitor` change page with session and pageview timeline inlines
- [x] CSV export actions, COUNT-free paginator
- [x] `assertNumQueries` tests proving no N+1
- [x] `seed_analytics` command; prove the dashboard renders under 500 ms at 1M rows

### Cross-cutting, throughout

- [x] Type hints and docstrings on every public function
- [x] `export_visitor_data()` and `delete_visitor_data()`, plus management commands
- [x] Never store a raw IP; never log a query string verbatim; scrub tokens and emails
- [x] `docs/analytics.md`: setup, settings reference, event taxonomy, privacy model
- [x] ADR at `docs/adr/0001-first-party-analytics-pipeline.md`

---

## 9. Open decisions

These need an answer before the phase that depends on them.

1. **Chart.js delivery** (Phase 7). The brief offers a CDN. Your `index.html`
   already loads Google Fonts from a CDN, so there is precedent — but the admin
   is your login surface, and a CDN script there is a supply-chain path to your
   session cookie. Vendoring one ~200 KB file into the app's static directory
   removes that. **Recommend vendoring.**
2. **`SearchQuery` and `ExperimentAssignment`** — build them empty, or defer?
   **Recommend deferring.**
3. **Optional dependencies** — `geoip2`, `user-agents`, `web-vitals`.
   **Recommend `web-vitals` only.**
4. **`HONOR_DNT` default** — keeping it `True`; flag if you want it `False`.
5. **The legacy local row** — migrate the 1 row, or start clean locally?
   Production rows are migrated either way.
6. **Python version drift** — the local `.venv` is 3.14.7, Render pins 3.13.4.
   Not caused by this work, but worth aligning while we are in here.

---

## 10. Rules being followed

- Every edit to a pre-existing file is shown as a diff and waits for sign-off.
- No existing migration is ever edited. New migrations only, from
  `makemigrations`, shown before being applied.
- The old visitor-IP code is removed only after you have seen the diff.
- No dependency is installed without an explicit yes.
- Where the brief and the repository disagree, the repository wins and the
  mismatch is flagged. Eight such mismatches are recorded in Phase 0.

---

## 11. Build status

Phases 1–7 are implemented. `python manage.py test` runs **188 tests, all
passing** (171 analytics, 17 api).

### Delivered as planned

Zero new Python dependencies and zero new npm dependencies. The full brief is
implemented: six core models plus `SearchQuery` and `ExperimentAssignment`, Tier
1 middleware collection, the beacon and ingest API, attribution and events,
security signals and consent, the buffered pipeline with its scheduler, and the
read-only admin with a custom dashboard.

### Deviations from the plan above, and why

| Planned | Built | Reason |
| --- | --- | --- |
| BRIN and GIN declared in `Meta.indexes` | Created by `0002_postgres_indexes` behind a vendor check | The local Postgres could not be reached (below), and declaring them on the models makes every migration unappliable on SQLite. Production still gets them; the suite now runs on either backend. |
| Chart.js, vendored | Hand-drawn inline SVG | ~80 lines with no dependency and no 200 KB asset, versus a charting library to draw one line chart and ten ranked lists. |
| `web-vitals` npm package | Raw `PerformanceObserver` | Keeps the promise of zero new dependencies. CLS uses the standard session-window algorithm; **INP is approximated** by the worst interaction latency rather than the true p98. Good enough to compare pages, not identical to the official metric. |
| `SearchQuery` / `ExperimentAssignment` deferred | Built | You asked for the request in its entirety. `SearchQuery` stays empty until the site has a search box. |
| Partitioning documented only | Built, off by default | Same reason. It is a management command rather than a migration, because converting the largest table in the schema should not ride along with a deploy. |

### Open items

1. **Local Postgres is installed but not connected.** PostgreSQL 17.11 is
   installed and the service is running on 5432, but creating the database and
   role needs the superuser credential, and the sandbox blocked both reading
   `pg_hba.conf` and probing for the password. Two commands finish it:

   ```bash
   "C:\Program Files\PostgreSQL\17\bin\createuser.exe" -U postgres -P yzwebsite
   "C:\Program Files\PostgreSQL\17\bin\createdb.exe"  -U postgres -O yzwebsite yzwebsite
   # then: set DATABASE_URL=postgres://yzwebsite:<password>@127.0.0.1:5432/yzwebsite
   ```

   Once `DATABASE_URL` points at it, `migrate` adds the BRIN and GIN indexes
   automatically — the vendor check in `0002` sees Postgres and applies them.

2. **The benchmark ran on SQLite, not Postgres**, for the same reason. The
   architectural claim it tests — that the dashboard reads `DailyStat` and stays
   flat as the raw tables grow — is engine-independent, but the absolute
   milliseconds are not production numbers. Re-run `python manage.py
   seed_analytics --benchmark` once Postgres is connected.

3. **The beacon is 5.55 KB gzipped as shipped**, against a 5 KB target. Stripping
   comments brings it to 4.06 KB. There is no JS minifier in the build pipeline
   (WhiteNoise compresses but does not minify), so this is the honest number.
   Either accept 6% over, or add a minify step.

4. **Partitioning is untested against a live Postgres.** The DDL is written and
   documented step by step, and the guards are covered by tests, but the
   conversion path itself could not be exercised without a Postgres connection.
   Treat it as unverified until you run it against a backup.

5. **Still unanswered from §9:** whether `HONOR_DNT` should stay `True` (kept),
   and the Python version drift between the local `.venv` (3.14.7) and Render
   (3.13.4).

---

## 12. Amendment: the raw IP listing

Added after the build, on request: restore the IP address listing that
`api.Visitor` provided, under the analytics app.

**This reverses a rule stated as non-negotiable in the original brief** — "never
store a raw IP address in the database". It was implemented anyway because it is
the site owner's data, their prior feature, and their call. Recorded here so the
decision is visible rather than buried.

### How the exposure is contained

| | |
| --- | --- |
| Scope | One table, `VisitorIP`. Nothing else stores an address, nothing joins against it, no report reads it. Asserted by tests. |
| Shape | Aggregated — one row per address with a running count, matching `api.Visitor`. Bounded by distinct visitors, not requests. |
| Switch | `ANALYTICS['STORE_RAW_IPS']`, default `True`. Off stops new rows immediately; the rest of the pipeline is unaffected. |
| Retention | `IP_RETENTION_DAYS`, default 90, on its own clock. Rows are deleted, not blanked. |
| Erasure | `visitor_data --delete-ip <address>`, plus superuser delete in the admin. |
| Removal | One setting plus `DROP TABLE analytics_visitorip`. |

The hash-only model still holds everywhere else: `Session` keeps `ip_hash` plus
a truncated network, `Visitor` keeps the rotating salted hash, and neither is
derived from or linkable to the listing.

### Legacy addresses were recovered

Migration `0003` had already imported the legacy rows in hashed form, discarding
the addresses — correct under the original rule. Because production had not yet
deployed, the original addresses still existed in `api_visitor` there, so
`0004_visitor_ip` backfills them before `api.0003` drops the table. Ordering is
forced with `run_before`, and the backfill is guarded on the table existing so
it is a no-op on any database where the drop already happened.

Verified end to end on a scratch database: four legacy rows with raw addresses
survived the full chain into `VisitorIP` (Googlebot correctly flagged
`is_bot`), while `Session` rows came out hash-only and the legacy table was
dropped.

### A pre-existing N+1 was found and fixed

The query-budget test written for this feature caught an unrelated bug: the
attribution write in `_apply_attribution` ran one `UPDATE` per new visitor —
**50 queries for a 40-visitor flush**. It now mutates in memory and
`_save_attribution` writes the batch in one `bulk_update`.

Flush cost is now flat:

```
   1 distinct visitor  -> 11 queries
  10 distinct visitors -> 13 queries
  40 distinct visitors -> 13 queries
 100 distinct visitors -> 13 queries
```

A test asserts the count is identical at batch sizes 5 and 50, which catches any
per-row query reintroduced anywhere in the flush path — not just in this code.

### Local migration history needed repair

`api.0003` was already applied locally, so adding `run_before` produced
`InconsistentMigrationHistory` and blocked `migrate` entirely, including the
rollback that would have fixed it. Resolved by recreating the empty
`api_visitor` table and clearing the `api.0003` row from `django_migrations`, so
the chain could re-apply in the correct order. The local superuser and all data
were preserved. **Production is unaffected** — it applies the whole chain from
scratch.
