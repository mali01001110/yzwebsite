"""
Resolution of a request's originating IP address.

`X-Forwarded-For` is a request header, which makes it visitor-controlled input:
anyone can send `X-Forwarded-For: 8.8.8.8` and, if the value were trusted
blindly, poison the visitor log with an address of their choosing. The header is
only meaningful to the extent that our own infrastructure wrote part of it.

Each proxy *appends* the address it received the connection from, so the
rightmost entries are the trustworthy ones and anything further left is whatever
the client chose to send. With `TRUSTED_PROXY_COUNT` hops in front of Django,
the real peer is the entry that many places from the right.
"""
import ipaddress

from django.conf import settings


def get_client_ip(request):
    """Return the visitor's IP address, or None if it cannot be determined."""
    trusted_proxy_count = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)

    if trusted_proxy_count > 0:
        forwarded_ip = _get_forwarded_ip(request, trusted_proxy_count)
        if forwarded_ip:
            return forwarded_ip

    # No proxy in front of us (or a malformed header): the socket peer is the
    # only address that cannot be forged.
    return _normalize_ip(request.META.get('REMOTE_ADDR'))


def is_public_ip(ip_address):
    """
    True for globally routable addresses.

    Loopback, private LAN, link-local and similar reserved ranges are not
    reachable from the public internet and say nothing about where a visitor
    came from.
    """
    parsed_ip = _parse_ip(ip_address)
    return bool(parsed_ip and parsed_ip.is_global)


def _get_forwarded_ip(request, trusted_proxy_count):
    forwarded_header = request.META.get('HTTP_X_FORWARDED_FOR', '')
    proxy_chain = [entry.strip() for entry in forwarded_header.split(',') if entry.strip()]

    # A chain shorter than the configured hop count means the header did not
    # come from the expected topology, so none of it can be trusted.
    if len(proxy_chain) < trusted_proxy_count:
        return None

    return _normalize_ip(proxy_chain[-trusted_proxy_count])


def _normalize_ip(raw_ip):
    """Validate and canonicalise an address so only real IPs reach the database."""
    parsed_ip = _parse_ip(raw_ip)
    return str(parsed_ip) if parsed_ip else None


def _parse_ip(raw_ip):
    if not raw_ip:
        return None
    try:
        # IPv6 arrives bracketed ('[::1]') from some front ends; ipaddress rejects that.
        return ipaddress.ip_address(raw_ip.strip().strip('[]'))
    except ValueError:
        return None
