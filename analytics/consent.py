"""
Consent state for a request.

Two categories, and they are not equivalent:

* **essential** — path, status code, timing, and a truncated IP for abuse
  investigation. Always collected. This is the data without which the site
  cannot be operated or defended, and it is what the old visitor-tracking
  middleware already collected.
* **analytics** — everything the browser beacon reports: engagement, scroll,
  clicks, errors, web vitals. Gated on ``ANALYTICS['REQUIRE_CONSENT']``.

``REQUIRE_CONSENT`` defaults to False for this project, on the site owner's
instruction that EU/UK consent regulation is out of scope. The machinery is
built and tested so flipping the setting is the only work needed to turn it on.

``DNT: 1`` and ``Sec-GPC: 1`` are honoured as a hard opt-out from the analytics
category regardless of cookie state, because they are browser-level signals
rather than any one jurisdiction's requirement — a person who set them has
already answered the question a banner would ask.
"""
from __future__ import annotations

from dataclasses import dataclass

from .defaults import get_setting

CATEGORY_ESSENTIAL = 'essential'
CATEGORY_ANALYTICS = 'analytics'

_AFFIRMATIVE = frozenset({'1', 'true', 'yes', 'granted', 'accepted'})


@dataclass(frozen=True)
class ConsentState:
    """What this visitor has agreed to, and why."""

    essential: bool = True
    analytics: bool = False
    reason: str = ''

    @property
    def allows_tier_two(self) -> bool:
        """Whether beacon data may be collected for this request."""
        return self.analytics


def read(request) -> ConsentState:
    """
    Resolve the consent state for one request.

    Order matters: an explicit browser opt-out beats a stored cookie, because
    the cookie may predate the visitor turning the signal on.
    """
    if _has_opt_out_signal(request):
        return ConsentState(analytics=False, reason='dnt')

    if not get_setting('REQUIRE_CONSENT'):
        return ConsentState(analytics=True, reason='not required')

    cookie = request.COOKIES.get(get_setting('CONSENT_COOKIE_NAME'), '')
    granted = _parse_cookie(cookie)
    return ConsentState(
        analytics=CATEGORY_ANALYTICS in granted,
        reason='cookie' if cookie else 'no cookie',
    )


def _has_opt_out_signal(request) -> bool:
    """True when the browser sent DNT: 1 or Sec-GPC: 1."""
    if not get_setting('HONOR_DNT'):
        return False
    meta = request.META
    return meta.get('HTTP_DNT') == '1' or meta.get('HTTP_SEC_GPC') == '1'


def _parse_cookie(value: str) -> frozenset[str]:
    """
    Read the consent cookie.

    Format is a comma-separated category list, optionally ``name:value`` pairs
    (``essential:1,analytics:0``). Both shapes are accepted because the banner
    writes the pair form and a hand-set cookie is likely to use the bare form.
    Anything unparseable grants nothing, which is the safe direction to fail.
    """
    granted: set[str] = set()
    for part in value.split(','):
        part = part.strip().lower()
        if not part:
            continue
        if ':' in part:
            name, _, flag = part.partition(':')
            if flag.strip() in _AFFIRMATIVE:
                granted.add(name.strip())
        else:
            granted.add(part)
    return frozenset(granted)


def build_cookie_value(analytics_granted: bool) -> str:
    """Return the cookie value representing a consent decision."""
    return f'{CATEGORY_ESSENTIAL}:1,{CATEGORY_ANALYTICS}:{"1" if analytics_granted else "0"}'
