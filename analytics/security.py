"""
Abuse and reconnaissance signals.

This module observes and records. It never blocks, never rate-limits and never
bans, because blocking has a blast radius — a false positive locks a real
visitor out of the site — and that is a decision for the site owner to make
separately, with this data in hand.

Three detectors, cheapest first:

* **Path scanning** — a 404 whose path contains a marker for software this site
  does not run. One request is enough to classify; no state needed.
* **ID enumeration** — a burst of 404/403 responses from one address inside a
  short window. Needs a counter, kept in memory rather than in the database.
* **Repeat offending** — the same address scanning several times, which
  separates a bored script from a targeted sweep.

The counters live in a bounded in-memory structure rather than in Postgres or a
cache backend. They are per-process, approximate, and reset on restart, and all
three of those are acceptable: the counter exists to decide whether to write a
row, not to be the record itself. The row is the record.
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from typing import Any

from django.http import HttpRequest

from .buffer import KIND_SECURITY, record
from .client_ip import get_client_ip
from .defaults import get_setting
from .geo import country_from_meta
from .models import SecurityEventKind
from .privacy import hash_ip, scrub, truncate_ip

# Paths shaped like a detail endpoint: a trailing numeric or UUID segment.
# Enumeration is only interesting on these — a sweep of /1, /2, /3 is probing
# for objects, whereas a sweep of random words is ordinary scanning.
_DETAIL_PATH = re.compile(
    r'/(?:\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$',
    re.IGNORECASE,
)

MAX_TRACKED_ADDRESSES = 2_000


class _RejectionTracker:
    """
    Per-address timestamps of recent rejected requests, bounded and expiring.

    Bounded because the keys come from the internet: an unbounded dict keyed by
    client address is a memory-exhaustion vector, so the least recently seen
    address is evicted once the table is full.
    """

    def __init__(self, max_addresses: int = MAX_TRACKED_ADDRESSES) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}
        self._scans: dict[str, int] = defaultdict(int)
        self._max_addresses = max_addresses

    def add_rejection(self, ip_hash: str, now: float, window: int) -> int:
        """Record a rejection and return how many fall inside the window."""
        with self._lock:
            self._evict_if_needed()
            timestamps = self._hits.setdefault(ip_hash, deque())
            timestamps.append(now)
            cutoff = now - window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            return len(timestamps)

    def add_scan(self, ip_hash: str) -> int:
        """Record a scan hit and return this address's running total."""
        with self._lock:
            self._scans[ip_hash] += 1
            return self._scans[ip_hash]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._scans.clear()

    def _evict_if_needed(self) -> None:
        if len(self._hits) < self._max_addresses:
            return
        # dicts preserve insertion order, so the first key is the oldest.
        oldest = next(iter(self._hits))
        self._hits.pop(oldest, None)
        self._scans.pop(oldest, None)


tracker = _RejectionTracker()


def observe_rejected_request(request: HttpRequest, status: int) -> None:
    """
    Classify a 403 or 404 and record a security event if it looks hostile.

    Called from the collector middleware, so it must stay cheap and must never
    raise into the response path.
    """
    path = request.path
    ip_address = get_client_ip(request)
    ip_hash = hash_ip(ip_address)
    now = time.time()

    matched = matched_scan_pattern(path)
    if matched:
        repeats = tracker.add_scan(ip_hash)
        _record(
            SecurityEventKind.PATH_SCAN,
            request,
            ip_address,
            ip_hash,
            path=path,
            metadata={
                'pattern': matched,
                'status': status,
                'repeat_count': repeats,
                'is_repeat_offender': repeats >= get_setting('SCAN_REPEAT_THRESHOLD'),
            },
        )
        return

    if _DETAIL_PATH.search(path):
        window = get_setting('ENUMERATION_WINDOW_SECONDS')
        hits = tracker.add_rejection(ip_hash, now, window)
        if hits >= get_setting('ENUMERATION_THRESHOLD'):
            _record(
                SecurityEventKind.ENUMERATION,
                request,
                ip_address,
                ip_hash,
                path=path,
                metadata={'hits_in_window': hits, 'window_seconds': window, 'status': status},
            )


def record_failed_login(request: HttpRequest | None, username: str) -> None:
    """Record a rejected credential attempt, from the ``user_login_failed`` signal."""
    ip_address = get_client_ip(request) if request is not None else None
    _record(
        SecurityEventKind.FAILED_LOGIN,
        request,
        ip_address,
        hash_ip(ip_address),
        path=getattr(request, 'path', '') if request is not None else '',
        # The attempted username is kept because a spray across many usernames
        # looks different from repeated attempts on one, and that distinction
        # is the whole value of the record. It is scrubbed in case someone
        # typed a password into the username field.
        username_attempted=scrub(username, max_length=150),
    )


def record_rate_limit(request: HttpRequest, scope: str, rate: str) -> None:
    """Record a throttle rejection. Called from the throttle class, not a signal."""
    ip_address = get_client_ip(request)
    _record(
        SecurityEventKind.RATE_LIMIT,
        request,
        ip_address,
        hash_ip(ip_address),
        path=getattr(request, 'path', ''),
        metadata={'scope': scope, 'rate': rate},
    )


def record_suspicious_user_agent(request: HttpRequest, reason: str) -> None:
    """Record a user agent that identifies as automated on a non-bot surface."""
    ip_address = get_client_ip(request)
    _record(
        SecurityEventKind.SUSPICIOUS_UA,
        request,
        ip_address,
        hash_ip(ip_address),
        path=getattr(request, 'path', ''),
        metadata={'reason': reason},
    )


def matched_scan_pattern(path: str) -> str | None:
    """Return the scan marker this path contains, if any."""
    lowered = path.lower()
    for pattern in get_setting('SCAN_PATTERNS'):
        if pattern in lowered:
            return pattern
    return None


def _record(
    kind: str,
    request: HttpRequest | None,
    ip_address: str | None,
    ip_hash: str,
    path: str = '',
    username_attempted: str = '',
    metadata: dict[str, Any] | None = None,
) -> None:
    meta = getattr(request, 'META', {}) if request is not None else {}
    record(
        KIND_SECURITY,
        # 'event_kind', not 'kind': the buffer already uses 'kind' to route a
        # record to its table, and SecurityEvent.kind is a different thing.
        event_kind=kind,
        ip_hash=ip_hash,
        ip_truncated=truncate_ip(ip_address),
        country=country_from_meta(meta),
        asn='',
        path=path[:200],
        username_attempted=username_attempted,
        occurred_at=time.time(),
        metadata=metadata or {},
    )
