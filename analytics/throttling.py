"""
Throttling for the ingest endpoint, with the rejection recorded.

DRF emits no signal when a request is throttled — ``rest_framework.throttling``
contains no ``Signal`` at all — so there is nothing to subscribe to. Logging
rate-limit hits therefore has to happen inside a throttle subclass, which is
what this is. The brief called for a signal; this is the only hook the library
actually offers.

The throttle keys on the resolved client address rather than DRF's default,
because the default reads ``REMOTE_ADDR`` and then ``X-Forwarded-For`` in a way
that trusts the header outright. Behind Cloudflare that would bucket every
visitor into the same key, or let one forge their way out of the limit.
"""
from __future__ import annotations

import logging

from rest_framework.throttling import SimpleRateThrottle

from . import security
from .client_ip import get_client_ip
from .defaults import get_setting
from .privacy import hash_ip

logger = logging.getLogger(__name__)


class IngestRateThrottle(SimpleRateThrottle):
    """Caps beacon submissions per address, and records each rejection."""

    scope = 'analytics_ingest'

    def get_rate(self) -> str:
        """
        Read the rate from the app's own settings.

        Overridden so the limit lives beside every other analytics setting
        rather than in REST_FRAMEWORK, which keeps the app removable in one
        piece.
        """
        return get_setting('INGEST_THROTTLE_RATE')

    def get_cache_key(self, request, view) -> str:
        # The hashed address, never the address itself: the throttle cache is
        # another place data comes to rest, and the same rule applies there.
        return self.cache_format % {
            'scope': self.scope,
            'ident': hash_ip(get_client_ip(request)) or 'anonymous',
        }

    def throttle_failure(self) -> bool:
        """Record the rejection, then let DRF return its 429."""
        try:
            security.record_rate_limit(self.request, self.scope, self.rate or '')
        except Exception:
            logger.exception('Could not record rate limit event')
        return super().throttle_failure()

    def allow_request(self, request, view) -> bool:
        # Stashed so throttle_failure, which DRF calls with no arguments, can
        # still reach the request it is rejecting.
        self.request = request
        return super().allow_request(request, view)
