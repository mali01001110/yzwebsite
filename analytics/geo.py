"""
Geographic and network enrichment.

Two sources, and the cheap one is the default:

* **Cloudflare's ``CF-IPCountry`` header** costs nothing. Cloudflare already
  proxies this domain and sends the header on every plan, so country-level
  reporting needs no dependency, no licence key, and no database to ship.
* **MaxMind GeoLite2**, behind ``ANALYTICS['GEOIP_ENABLED']``, adds city,
  coordinates, timezone and ASN. It needs the ``geoip2`` package and two
  ``.mmdb`` files. Off by default.

Everything here fails soft. A missing database, an unreadable file or a
malformed address returns empty enrichment — never an exception. Analytics is
not permitted to be the reason a page fails to render, and this module runs in
the pipeline worker where an unhandled error would kill the flush thread.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from .defaults import get_setting

logger = logging.getLogger(__name__)

# Hosting and cloud providers, matched as substrings against the ASN
# organisation name. A visitor is not browsing a portfolio from an AWS
# instance, so this is the single most reliable cheap bot signal available.
DATACENTER_KEYWORDS = (
    'amazon', 'aws', 'google cloud', 'google llc', 'microsoft', 'azure',
    'digitalocean', 'linode', 'akamai', 'cloudflare', 'ovh', 'hetzner',
    'vultr', 'scaleway', 'contabo', 'leaseweb', 'rackspace', 'oracle cloud',
    'alibaba', 'tencent', 'choopa', 'quadranet', 'colocrossing', 'hosting',
    'datacenter', 'data center', 'server', 'vps', 'cloud',
)


@dataclass
class GeoResult:
    """What could be learned about where a request came from."""

    country: str = ''
    region: str = ''
    city: str = ''
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    tz_from_ip: str = ''
    asn: str = ''
    asn_org: str = ''
    is_datacenter: bool = False

    def as_session_fields(self) -> dict[str, Any]:
        """Return this result shaped for ``Session(**fields)``."""
        return {
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'tz_from_ip': self.tz_from_ip,
            'asn': self.asn,
            'asn_org': self.asn_org,
            'is_datacenter': self.is_datacenter,
        }


def country_from_meta(meta: dict) -> str:
    """
    Return the ISO country code Cloudflare attached to the request.

    Cloudflare uses 'XX' for unknown and 'T1' for Tor exit nodes; neither is a
    country, so both become empty.
    """
    raw = (meta.get(get_setting('COUNTRY_HEADER')) or '').strip().upper()
    if len(raw) != 2 or raw in ('XX', 'T1'):
        return ''
    return raw


def lookup(ip_address: str | None, country_hint: str = '') -> GeoResult:
    """
    Enrich an address as far as the configured sources allow.

    ``country_hint`` is the Cloudflare header value, used as the answer when
    MaxMind is disabled and as a fallback when its lookup misses.
    """
    result = GeoResult(country=country_hint)
    if not ip_address or not get_setting('GEOIP_ENABLED'):
        return result

    reader = _city_reader()
    if reader is not None:
        try:
            city = reader.city(ip_address)
            result.country = (city.country.iso_code or country_hint or '')[:2]
            result.region = (city.subdivisions.most_specific.name or '')[:80]
            result.city = (city.city.name or '')[:80]
            result.tz_from_ip = (city.location.time_zone or '')[:64]
            if city.location.latitude is not None:
                result.latitude = Decimal(str(round(city.location.latitude, 5)))
            if city.location.longitude is not None:
                result.longitude = Decimal(str(round(city.location.longitude, 5)))
        except Exception:
            # AddressNotFoundError for unroutable addresses is routine, not an
            # error worth a stack trace on every private-range request.
            logger.debug('GeoIP city lookup missed', exc_info=True)

    asn_reader = _asn_reader()
    if asn_reader is not None:
        try:
            asn = asn_reader.asn(ip_address)
            result.asn = str(asn.autonomous_system_number or '')[:16]
            result.asn_org = (asn.autonomous_system_organization or '')[:160]
            result.is_datacenter = is_datacenter_org(result.asn_org)
        except Exception:
            logger.debug('GeoIP ASN lookup missed', exc_info=True)

    return result


def is_datacenter_org(organisation: str) -> bool:
    """True when an ASN organisation name reads as hosting rather than an ISP."""
    lowered = (organisation or '').lower()
    return any(keyword in lowered for keyword in DATACENTER_KEYWORDS)


def database_status() -> dict[str, Any]:
    """Report which GeoIP databases are present, for the management command."""
    directory = get_setting('GEOIP_PATH')
    if not directory:
        return {'enabled': get_setting('GEOIP_ENABLED'), 'path': None, 'files': {}}

    base = Path(directory)
    return {
        'enabled': get_setting('GEOIP_ENABLED'),
        'path': str(base),
        'files': {
            name: (base / name).exists()
            for name in (
                get_setting('GEOIP_CITY_FILENAME'),
                get_setting('GEOIP_ASN_FILENAME'),
            )
        },
    }


def reset_readers() -> None:
    """Drop cached readers, so a freshly downloaded database is picked up."""
    _city_reader.cache_clear()
    _asn_reader.cache_clear()


@lru_cache(maxsize=1)
def _city_reader():
    return _open_reader(get_setting('GEOIP_CITY_FILENAME'))


@lru_cache(maxsize=1)
def _asn_reader():
    return _open_reader(get_setting('GEOIP_ASN_FILENAME'))


def _open_reader(filename: str):
    """
    Open one .mmdb file, or return None if it cannot be used.

    The reader is cached for the process lifetime because mmdb files are
    memory-mapped: reopening per lookup would be pure syscall overhead.
    """
    directory = get_setting('GEOIP_PATH')
    if not directory:
        logger.warning('ANALYTICS["GEOIP_ENABLED"] is on but GEOIP_PATH is unset.')
        return None

    path = Path(directory) / filename
    if not path.exists():
        logger.warning('GeoIP database missing: %s', path)
        return None

    try:
        import geoip2.database
    except ImportError:
        logger.warning(
            'ANALYTICS["GEOIP_ENABLED"] is on but the geoip2 package is not '
            'installed. Country still resolves from the Cloudflare header.'
        )
        return None

    try:
        return geoip2.database.Reader(str(path))
    except Exception:
        logger.exception('Could not open GeoIP database at %s', path)
        return None
