"""
Request-time collection. Replaces ``api.middleware.VisitorTrackingMiddleware``.

The hard rule this file exists to satisfy: **no database access in the request
path**. Everything here builds a plain dict of primitives and appends it to the
in-process buffer. The pipeline worker does the lookups, the parsing, the bot
scoring and the writes.

Placed last in ``MIDDLEWARE``, which the previous implementation also did and
for the same reason: it only records requests that made it through every other
layer, and by then ``request.user`` and the session are resolved and the
response's status and content type are known.

Only the response phase does any work. Deciding on the way in would mean
guessing whether a path is a page, an asset or an API call; deciding on the way
out means reading the status code and content type and knowing.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse

from . import consent, security
from .buffer import KIND_PAGEVIEW, record
from .client_ip import get_client_ip
from .defaults import get_setting
from .geo import country_from_meta
from .privacy import (
    allowlisted_params,
    hash_ip,
    hash_query_string,
    hash_visitor,
    safe_referrer,
)
from .useragent import client_hints_from_meta

logger = logging.getLogger(__name__)

# Asks the browser to send high-entropy client hints on subsequent requests.
# Without this only the low-entropy subset arrives, which omits platform
# version entirely.
ACCEPT_CH_HEADER = (
    'Sec-CH-UA, Sec-CH-UA-Platform, Sec-CH-UA-Mobile, Sec-CH-UA-Platform-Version'
)

MAX_LANGUAGE_LENGTH = 35
MAX_PATH_LENGTH = 200


class ConsentMiddleware:
    """
    Attaches the resolved consent state to the request.

    Separate from the collector so that views, the ingest endpoint and the
    template context can all read one authoritative answer, computed once.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.analytics_consent = consent.read(request)
        return self.get_response(request)


class CollectorMiddleware:
    """
    Records one buffered pageview per HTML page a visitor successfully loads.

    Also feeds the security detectors, which is why 404s and 403s reach it even
    though they are not pageviews.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not get_setting('ENABLED'):
            return self.get_response(request)

        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        try:
            self._observe(request, response, elapsed_ms)
        except Exception:
            # Collection is incidental to serving the page. A failure here must
            # never turn a working response into a 500 for the visitor.
            logger.exception('Analytics collection failed for %s', request.path)

        if self._is_html(response):
            response.headers['Accept-CH'] = ACCEPT_CH_HEADER

        return response

    def _observe(self, request: HttpRequest, response: HttpResponse, elapsed_ms: int) -> None:
        if self._is_excluded(request.path):
            return

        status = response.status_code

        # Security signals come from the requests that failed, so they are
        # evaluated before the pageview test rejects them.
        if status in (403, 404):
            security.observe_rejected_request(request, status)
            if status == 404:
                self._record_not_found(request, response, elapsed_ms)
            return

        if self._is_pageview(request, response):
            self._record_pageview(request, response, elapsed_ms, status)

    def _record_pageview(
        self,
        request: HttpRequest,
        response: HttpResponse,
        elapsed_ms: int,
        status: int,
    ) -> None:
        record(KIND_PAGEVIEW, **self._build(request, elapsed_ms, status))

    def _record_not_found(
        self, request: HttpRequest, response: HttpResponse, elapsed_ms: int
    ) -> None:
        """
        Record 404s with their referrer, which is what makes broken inbound
        links findable. A 404 has no session worth starting, so it is stored
        as a pageview with its status rather than as a visit.
        """
        if not self._wants_html(request):
            return
        record(KIND_PAGEVIEW, **self._build(request, elapsed_ms, 404))

    def _build(self, request: HttpRequest, elapsed_ms: int, status: int) -> dict[str, Any]:
        """
        Assemble the buffered record.

        Everything expensive is deliberately absent: no geo database read, no
        regex-heavy UA parse, no query. Those happen in the worker. What is
        done here is string slicing and two hashes, which is what keeps the
        added latency under the 1 ms target.
        """
        meta = request.META
        ip_address = get_client_ip(request)
        user_agent = meta.get('HTTP_USER_AGENT', '')
        referrer_host, referrer_url = safe_referrer(meta.get('HTTP_REFERER'))
        params = allowlisted_params(request.META.get('QUERY_STRING', ''))
        consent_state = getattr(request, 'analytics_consent', None)

        user = getattr(request, 'user', None)
        user_id = user.pk if user is not None and user.is_authenticated else None

        return {
            'visitor_id': hash_visitor(ip_address, user_agent),
            'ip_hash': hash_ip(ip_address),
            # The raw address goes no further than this dict, and the pipeline
            # truncates it before writing. It is carried rather than truncated
            # here because the geo lookup needs full precision.
            'ip_address': ip_address,
            'user_agent': user_agent[:400],
            'client_hints': client_hints_from_meta(meta),
            'path': request.path[:MAX_PATH_LENGTH],
            'query_hash': hash_query_string(meta.get('QUERY_STRING', '')),
            'params': params,
            'referrer_host': referrer_host,
            'referrer_url': referrer_url,
            'country_hint': country_from_meta(meta),
            'language': meta.get('HTTP_ACCEPT_LANGUAGE', '')[:MAX_LANGUAGE_LENGTH],
            'status_code': status,
            'response_ms': elapsed_ms,
            'user_id': user_id,
            'occurred_at': time.time(),
            'consent_analytics': bool(consent_state and consent_state.analytics),
            'is_spa_navigation': False,
        }

    @staticmethod
    def _is_excluded(path: str) -> bool:
        """
        True for paths this app must not record.

        Defaults are derived from ``BACKEND_PREFIXES`` in the root URLconf plus
        the files WhiteNoise serves out of ``frontend/dist``.
        """
        if path in get_setting('EXCLUDE_PATHS'):
            return True
        return path.startswith(tuple(get_setting('EXCLUDE_PATH_PREFIXES')))

    @staticmethod
    def _is_pageview(request: HttpRequest, response: HttpResponse) -> bool:
        """
        True only for a browser successfully loading a page.

        Filtering on the rendered content type means static assets, JSON
        responses and redirects are excluded without listing their URLs here —
        the same test the previous implementation used, kept because it is
        correct and because it needs no knowledge of the URL configuration.
        """
        if request.method != 'GET' or response.status_code != 200:
            return False
        return CollectorMiddleware._is_html(response)

    @staticmethod
    def _is_html(response: HttpResponse) -> bool:
        return response.headers.get('Content-Type', '').startswith('text/html')

    @staticmethod
    def _wants_html(request: HttpRequest) -> bool:
        """True when the client asked for a page rather than an asset."""
        return 'text/html' in request.META.get('HTTP_ACCEPT', '')
