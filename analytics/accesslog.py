"""
Reconstruction of pageviews from a gunicorn access log.

Exists because of a gap in the record rather than as a feature: between the
analytics app's deployment and the fix to :func:`analytics.pipeline.start_scheduler`,
a preloading gunicorn left every worker without a pipeline thread, so the
records those workers buffered were evicted unwritten. The access log is the
only surviving trace of that traffic.

**What it cannot recover, and why.** The log's client column is the platform's
internal load balancer, not the visitor: the real address arrived in
``CF-Connecting-IP``, which gunicorn's default format does not write. Every
consequence of that is permanent. There is no address, so no ``VisitorIP`` row,
no ``ip_hash``, no truncated address and no geo lookup. ``visitor_id`` is
derived from address, user agent and a daily salt, and those salts rotated and
were discarded, so real identifiers cannot be recomputed either.

What the log does hold is a timestamp, a path, a status, a referrer and a user
agent, which is enough for a pageview and for the browser, OS, device and bot
classification drawn from it.

**Identity is synthesised, and coarser than the real thing.** Visitors are keyed
on user agent and calendar day, so everyone sharing a user agent on one day
collapses into a single visitor. Pageview and session counts are therefore
sound while unique-visitor counts are a floor, not a measurement. The salt is
fixed and distinct from the live one so an imported visitor can never collide
with a recorded one, the same reasoning
``0003_migrate_legacy_visitors`` applies to the rows it carried over.

Records built here are handed to :func:`analytics.buffer.record` in the shape
the collector middleware produces, so sessionization, channel classification
and bot scoring all run through the pipeline that writes live traffic rather
than through a second implementation of it.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from .middleware import MAX_PATH_LENGTH, CollectorMiddleware
from .models import Visitor
from .privacy import allowlisted_params, safe_referrer

# Fixed rather than derived from SECRET_KEY, so a re-import in another
# environment produces the same identifiers and the same rows.
IMPORT_SALT = 'analytics-access-log-import-v1'

# Written to Session.import_source on every row this module produces. The
# marker is what makes a reconstructed session separable from a recorded one
# forever after, in the admin and in any query.
DEFAULT_IMPORT_SOURCE = 'access-log'

# gunicorn's default access format:
#   %(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"
LINE_PATTERN = re.compile(
    r'^(?P<host>\S+) \S+ \S+ '
    r'\[(?P<time>[^\]]+)\] '
    r'"(?P<request>[^"]*)" '
    r'(?P<status>\d{3}) (?P<bytes>\S+) '
    r'"(?P<referrer>[^"]*)" '
    r'"(?P<agent>[^"]*)"'
)

TIME_FORMAT = '%d/%b/%Y:%H:%M:%S %z'

# Matches the ceiling the collector middleware applies to the same field.
USER_AGENT_MAX_LENGTH = 400

# The log records no content type, which is what the middleware actually tests
# to tell a page from an asset. Extension is the closest available substitute:
# anything ending in one of these was a file, whatever its status code said.
NON_PAGE_EXTENSIONS = frozenset({
    '.js', '.mjs', '.css', '.map', '.json', '.xml', '.txt', '.pdf',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.avif', '.bmp',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp4', '.webm', '.mp3', '.wav', '.zip', '.gz',
})


@dataclass(frozen=True)
class AccessLogEntry:
    """One parsed line. Only the fields a pageview can be built from."""

    occurred_at: datetime
    method: str
    path: str
    query_string: str
    status: int
    referrer: str
    user_agent: str


def parse_line(line: str) -> AccessLogEntry | None:
    """
    Parse one access-log line, or return None if it is not one.

    Returning None rather than raising is deliberate: a real log is
    interleaved with the platform's own output and with gunicorn's lifecycle
    messages, and none of that is an error worth stopping an import for.
    """
    match = LINE_PATTERN.match(line.strip())
    if match is None:
        return None

    try:
        occurred_at = datetime.strptime(match['time'], TIME_FORMAT)
    except ValueError:
        return None

    request_parts = match['request'].split()
    if len(request_parts) < 2:
        return None

    method, target = request_parts[0], request_parts[1]
    split_target = urlsplit(target)
    referrer = match['referrer']

    return AccessLogEntry(
        occurred_at=occurred_at,
        method=method.upper(),
        path=split_target.path or '/',
        query_string=split_target.query,
        status=int(match['status']),
        # gunicorn writes '-' for an absent referrer.
        referrer='' if referrer == '-' else referrer,
        user_agent=match['agent'],
    )


def is_pageview(entry: AccessLogEntry) -> bool:
    """
    True for a line the collector would have recorded as a pageview.

    Mirrors ``CollectorMiddleware`` as closely as the log allows: same method
    and status test, same exclusion list, with the content-type test replaced
    by the extension check the log makes necessary.
    """
    if entry.method != 'GET' or entry.status != 200:
        return False
    if CollectorMiddleware._is_excluded(entry.path):
        return False
    return not _looks_like_asset(entry.path)


def to_record(
    entry: AccessLogEntry,
    import_source: str = DEFAULT_IMPORT_SOURCE,
) -> dict:
    """
    Build the buffered record the middleware would have produced for this line.

    Every field the log cannot answer is left at the value that means "not
    known" rather than guessed at, so a reconstructed row never claims more
    than the log actually said.
    """
    referrer_host, referrer_url = safe_referrer(entry.referrer or None)

    return {
        'visitor_id': synthetic_visitor_id(entry.user_agent, entry.occurred_at),
        'ip_hash': '',
        'ip_address': None,
        'user_agent': entry.user_agent[:USER_AGENT_MAX_LENGTH],
        'client_hints': {},
        'path': entry.path[:MAX_PATH_LENGTH],
        # The live hash is salted with a rotating secret that no longer exists,
        # so any value here would be a different hash of the same string and
        # would never match a recorded one.
        'query_hash': '',
        'params': allowlisted_params(entry.query_string),
        'referrer_host': referrer_host,
        'referrer_url': referrer_url,
        'country_hint': '',
        'language': '',
        'status_code': entry.status,
        'response_ms': None,
        'user_id': None,
        'occurred_at': entry.occurred_at,
        'consent_analytics': False,
        'is_spa_navigation': False,
        'import_source': import_source,
    }


def synthetic_visitor_id(user_agent: str, occurred_at: datetime) -> str:
    """
    A stable identifier for one user agent on one day.

    Keyed on the day because the live identifier rotates daily and a
    reconstructed one that persisted across days would overstate returning
    visitors rather than understating them. Understating is the safer error
    here: it is visible as a low number, where the other is invisible.
    """
    key = f'{occurred_at.date().isoformat()}|{user_agent}'
    digest = hmac.new(IMPORT_SALT.encode(), key.encode(), hashlib.sha256)
    return digest.hexdigest()[:Visitor.ID_LENGTH]


def _looks_like_asset(path: str) -> bool:
    tail = path.rsplit('/', 1)[-1]
    if '.' not in tail:
        return False
    return f'.{tail.rsplit(".", 1)[-1].lower()}' in NON_PAGE_EXTENSIONS
