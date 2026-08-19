"""
The privacy primitives every other module is required to go through.

Three rules are enforced here, and nowhere else needs to reimplement them:

1. **No raw IP address is ever written.** Callers get a salted hash plus a
   truncated address, and the original is discarded.
2. **The visitor hash rotates daily.** ``visitor_id`` is derived from a salt
   that changes every 24 hours, which yields stable daily uniques while making
   the identifier useless the following day. Old salts are not retained.
3. **Nothing token-, email- or password-shaped is stored.** Free text from the
   browser — error messages, event properties — is scrubbed on the way in.

The daily salt is derived from ``SECRET_KEY`` and the current period rather than
generated and stored. That means no salt table to leak, and every process
derives the same value without coordination. Rotating ``SECRET_KEY`` therefore
also rotates every visitor identifier, which is the correct behaviour.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from django.conf import settings

from .defaults import get_setting

HASH_LENGTH = 64

# Mirrors Session.HOST_MAX_LENGTH / Session.URL_MAX_LENGTH. Duplicated as plain
# constants rather than imported: this module is on the request path and
# pulling the model layer into its import chain buys nothing.
REFERRER_HOST_MAX_LENGTH = 120
REFERRER_URL_MAX_LENGTH = 500

# Applied to any free text that originates in the browser. Deliberately broad:
# a false positive costs a redacted debug string, a false negative writes a
# credential to the database.
_SCRUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Email addresses.
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), '[email]'),
    # JWTs: three base64url segments separated by dots.
    (re.compile(r'\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}\b'), '[jwt]'),
    # Bearer / token / key / secret / password assignments in any punctuation style.
    (re.compile(
        r'(?i)\b(?:bearer|token|api[_-]?key|secret|password|passwd|pwd|auth|'
        r'session|csrf)\b\s*[:=]?\s*[\'"]?[\w./+-]{6,}[\'"]?'
    ), '[redacted]'),
    # Long opaque strings: 32+ chars of base64/hex alphabet with no spaces.
    (re.compile(r'\b[A-Za-z0-9_-]{32,}\b'), '[opaque]'),
    # Anything that looks like a raw IPv4 address, so an IP cannot sneak in
    # through a free-text field and defeat rule 1.
    (re.compile(r'\b\d{1,3}(?:\.\d{1,3}){3}\b'), '[ip]'),
)


def current_salt(now: datetime | None = None) -> str:
    """
    Return the salt for the current rotation period.

    Derived rather than stored, so there is no salt to steal and no
    coordination between processes. The period number is the count of rotation
    windows since the Unix epoch, which makes the boundary identical everywhere
    regardless of local timezone.
    """
    now = now or datetime.now(timezone.utc)
    window_seconds = get_setting('SALT_ROTATION_HOURS') * 3600
    period = int(now.timestamp()) // window_seconds
    return hashlib.sha256(
        f'{settings.SECRET_KEY}:analytics-salt:{period}'.encode()
    ).hexdigest()


def hash_visitor(ip_address: str | None, user_agent: str, now: datetime | None = None) -> str:
    """
    Return the rotating pseudonymous identifier for one visitor.

    HMAC rather than a plain hash of salt+data: with a plain concatenation an
    attacker who learns the salt can extend it, and the IP space is small
    enough (2^32) to brute-force either way. HMAC is the correct construction
    for keyed hashing and costs nothing extra here.
    """
    message = f'{ip_address or "unknown"}|{user_agent}'.encode()
    return hmac.new(
        current_salt(now).encode(), message, hashlib.sha256
    ).hexdigest()[:HASH_LENGTH]


def hash_ip(ip_address: str | None, salt: str | None = None) -> str:
    """Return a keyed hash of an address, for grouping abuse without storing it."""
    if not ip_address:
        return ''
    return hmac.new(
        (salt or current_salt()).encode(), ip_address.encode(), hashlib.sha256
    ).hexdigest()[:HASH_LENGTH]


def truncate_ip(ip_address: str | None) -> str | None:
    """
    Return the address with its host portion zeroed.

    IPv4 keeps 24 bits and IPv6 keeps 48, which identifies a network without
    identifying a subscriber. Returns None for anything unparseable, so a
    malformed value can never reach a GenericIPAddressField.
    """
    if not ip_address:
        return None
    try:
        parsed = ipaddress.ip_address(ip_address.strip().strip('[]'))
    except ValueError:
        return None

    prefix = 24 if parsed.version == 4 else 48
    network = ipaddress.ip_network(f'{parsed}/{prefix}', strict=False)
    return str(network.network_address)


def hash_query_string(query: str) -> str:
    """
    Return an opaque digest of the non-allowlisted part of a query string.

    Query strings routinely carry password-reset tokens, signed URLs and
    session identifiers, so the raw value is never stored. The digest still
    distinguishes one parameter set from another for counting purposes.
    """
    if not query:
        return ''

    allowlist = set(get_setting('QUERY_PARAM_ALLOWLIST'))
    remainder = sorted(
        (key, value) for key, value in parse_qsl(query, keep_blank_values=True)
        if key not in allowlist
    )
    if not remainder:
        return ''

    canonical = '&'.join(f'{key}={value}' for key, value in remainder)
    return hashlib.sha256(canonical.encode()).hexdigest()[:HASH_LENGTH]


def allowlisted_params(query: str) -> dict[str, str]:
    """Return only the query parameters that are safe to store in the clear."""
    allowlist = set(get_setting('QUERY_PARAM_ALLOWLIST'))
    return {
        key: value
        for key, value in parse_qsl(query, keep_blank_values=True)
        if key in allowlist
    }


def scrub(text: str | None, max_length: int = 500) -> str:
    """
    Remove anything credential- or contact-shaped from browser-supplied text.

    Applied to JS error messages, stack traces and string event properties
    before they are written.
    """
    if not text:
        return ''
    cleaned = str(text)
    for pattern, replacement in _SCRUB_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned[:max_length]


def scrub_props(props: Any, depth: int = 0) -> Any:
    """
    Recursively scrub a JSON-shaped event payload.

    Depth is capped because the structure comes from the browser and a deeply
    nested object would otherwise be a cheap way to burn server CPU.
    """
    if depth > 5:
        return None
    if isinstance(props, dict):
        return {
            str(key)[:60]: scrub_props(value, depth + 1)
            for key, value in list(props.items())[:50]
        }
    if isinstance(props, (list, tuple)):
        return [scrub_props(item, depth + 1) for item in list(props)[:50]]
    if isinstance(props, str):
        return scrub(props, max_length=500)
    if isinstance(props, (int, float, bool)) or props is None:
        return props
    return scrub(str(props))


def safe_referrer(referrer: str | None) -> tuple[str, str]:
    """
    Return ``(host, url)`` for a referrer, with its query string dropped.

    A referrer's query string belongs to somebody else's site and can carry
    their users' tokens, so only scheme, host and path are kept.
    """
    if not referrer:
        return '', ''
    try:
        parts = urlsplit(referrer)
    except ValueError:
        return '', ''
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return '', ''

    host = parts.hostname.lower()[:REFERRER_HOST_MAX_LENGTH]
    url = f'{parts.scheme}://{host}{parts.path}'[:REFERRER_URL_MAX_LENGTH]
    return host, url
