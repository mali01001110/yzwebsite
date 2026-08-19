# 1. Run the analytics pipeline inside the web process

Date: 2026-08-19

Status: **Proposed** — awaiting approval alongside `docs/analytics-plan.md`.

## Context

The site needs first-party visitor analytics with no third-party script and no
data leaving the project's own Postgres database. The collection middleware must
not write to the database synchronously, so collected rows have to be buffered
somewhere and flushed by something other than the request that produced them.
Aggregation, sessionization and retention also need to run on a schedule.

The conventional answer is Redis as a write buffer plus Celery workers and Celery
Beat for the scheduled jobs. Neither exists in this project today: `render.yaml`
declares one web service and one Postgres database, and there is no Celery,
Redis, or cron anywhere in the codebase.

Two constraints decide this:

- Measured traffic is **under ~500 pageviews per day**. That is roughly 182k
  `PageView` rows per year — three to four orders of magnitude below where a
  Redis buffer or table partitioning starts to pay for itself.
- The budget for new infrastructure is **zero**. On Render, a Key Value instance
  and a background worker are each separately billed services.

`CLAUDE.md` also requires KISS and YAGNI, and forbids speculative features and
premature abstraction. A Celery topology sized for traffic this project does not
have would violate all three.

## Decision

Run the entire pipeline inside the existing `starter` web service.

- **Buffer.** An in-process `collections.deque`. The middleware builds a plain
  dict, appends it, and returns. No database access in the request path.
- **Worker.** One daemon thread, started from `AppConfig.ready()`, which flushes
  the buffer with `bulk_create()` every 5 seconds or 500 rows, and runs
  enrichment, sessionization, the daily rollup and retention on their own
  intervals.
- **Concurrency guard.** `pg_try_advisory_lock` around every scheduled job, so
  additional gunicorn workers can never double-run one. The current
  `startCommand` uses gunicorn's default of a single worker, but the lock makes
  scaling out safe without a code change.
- **Escape hatch.** Every scheduled job is also a management command, and the
  thread is disabled with `ANALYTICS['RUN_INLINE_SCHEDULER'] = False`. Moving to
  Render Cron, GitHub Actions, or a real Celery worker later is a configuration
  change, not a rewrite.
- **Geo enrichment** uses Cloudflare's `CF-IPCountry` header rather than MaxMind
  GeoLite2. Cloudflare already proxies the domain and sends the header on every
  plan, which gives country for free with no dependency, no licence key, and no
  70 MB download on each deploy. MaxMind stays available behind
  `ANALYTICS['GEOIP_ENABLED']` for city, coordinates and ASN.

## Consequences

**Good**

- No new billed services and no new Python dependencies.
- The hard requirement of zero synchronous database writes in the request path
  is met.
- Far less to review, and removing the app removes the whole feature — no
  orphaned worker or queue to clean up.
- Local development needs no Redis or worker process to exercise the real code
  path.

**Bad**

- Rows buffered but not yet flushed are lost if the instance restarts inside the
  flush window. At this volume that is a handful of rows per deploy. Accepted.
- The flush thread competes with request handling for the GIL. At 500 pageviews
  per day the thread is idle almost all the time.
- The scheduler only runs while the web service is running. The `starter` plan
  does not spin down, so this holds; it would not on the free tier.
- Jobs must be written to catch up after downtime rather than assuming they ran
  exactly on schedule. This is required anyway, since every job has to be
  idempotent and re-runnable.

**Revisit when** sustained traffic exceeds roughly 10k pageviews per day, or a
second web instance is added, or losing a flush window stops being acceptable.
At that point the management commands move to Render Cron first, and Celery only
if that proves insufficient.
