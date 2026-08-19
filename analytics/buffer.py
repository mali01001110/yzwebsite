"""
The in-process write buffer that keeps the request path free of database work.

The middleware builds a plain dict and appends it here. A daemon thread in
:mod:`analytics.pipeline` drains the buffer and writes it in bulk. Appending is
a ``deque.append`` behind a lock held for the duration of one pointer swap, so
the cost added to a request is a few microseconds and never a query.

Why a deque and not Redis: at this site's volume a Redis round trip would cost
more than the database write it avoids, and it would add a billed service and a
dependency. The trade is that rows buffered but not yet flushed are lost if the
process dies inside the flush window. See
``docs/adr/0001-first-party-analytics-pipeline.md``.

``maxlen`` is the safety valve. If the database is unreachable the buffer stops
growing and starts discarding its oldest entries, because analytics must never
be the reason the site runs out of memory.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any

from .defaults import get_setting

logger = logging.getLogger(__name__)

# Every buffered record is a dict carrying this key, which tells the pipeline
# which table it belongs in.
KIND_PAGEVIEW = 'pageview'
KIND_EVENT = 'event'
KIND_SECURITY = 'security'
KIND_SEARCH = 'search'


class RecordBuffer:
    """
    A bounded, thread-safe queue of pending analytics records.

    Not a ``queue.Queue``: the consumer wants to drain everything at once for a
    single ``bulk_create``, and Queue offers no atomic drain. A deque plus one
    lock does exactly what is needed and nothing more.
    """

    def __init__(self, hard_limit: int | None = None) -> None:
        self._lock = threading.Lock()
        self._records: deque[dict[str, Any]] = deque(
            maxlen=hard_limit or get_setting('BUFFER_HARD_LIMIT')
        )
        self._dropped = 0

    def append(self, record: dict[str, Any]) -> None:
        """
        Queue one record. Never raises, never blocks on anything but the lock.

        A full deque silently evicts from the left, so the counter is how we
        find out it happened.
        """
        with self._lock:
            if len(self._records) == self._records.maxlen:
                self._dropped += 1
            self._records.append(record)

    def drain(self) -> list[dict[str, Any]]:
        """
        Remove and return everything currently buffered.

        Swaps in a fresh deque rather than popping one at a time, so the lock
        is held for a pointer assignment instead of for the length of the
        batch. Producers block for microseconds regardless of batch size.
        """
        with self._lock:
            if not self._records:
                return []
            drained = self._records
            self._records = deque(maxlen=drained.maxlen)
            dropped, self._dropped = self._dropped, 0

        if dropped:
            logger.error(
                'Analytics buffer overflowed: %d record(s) discarded. The '
                'flush thread is not keeping up, or the database is down.',
                dropped,
            )
        return list(drained)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def is_full_enough_to_flush(self) -> bool:
        """True once the buffer has reached the configured batch size."""
        return len(self) >= get_setting('BUFFER_MAX_ROWS')

    def clear(self) -> None:
        """Discard everything. Used by tests to isolate cases."""
        with self._lock:
            self._records.clear()
            self._dropped = 0


# One buffer per process. Module-level rather than injected because the
# middleware, the signal handlers and the flush thread all need the same
# instance and threading it through every call site would buy nothing.
buffer = RecordBuffer()


def record(kind: str, **fields: Any) -> None:
    """Queue one record of the given kind. The only entry point callers need."""
    if not get_setting('ENABLED'):
        return
    buffer.append({'kind': kind, **fields})
