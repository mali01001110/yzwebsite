"""
Browser, OS and device identification without a dependency.

Two sources, in priority order:

1. **Client hints** (``Sec-CH-UA`` and friends). Structured, sent by Chromium
   browsers, and not a guess — when present they are simply correct. The
   collector sends an ``Accept-CH`` response header to ask for them.
2. **The user-agent string**, parsed by the ordered rules below. Only consulted
   for what the hints did not supply, which in practice means Safari and
   Firefox.

The rule table is ordered because user-agent strings lie by design: Edge
contains "Chrome", Chrome contains "Safari", and almost everything contains
"Mozilla/5.0". First match wins, so the most specific token is listed first.

This replaces the ``user-agents`` package, which would have pulled in three
dependencies to do the same job. The trade is coverage of long-tail and legacy
browsers, which this deliberately does not attempt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .defaults import get_setting

MAX_UA_LENGTH = 400

# (label, pattern). Order matters — see the module docstring.
_BROWSER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ('Edge', re.compile(r'Edg(?:e|A|iOS)?/([\d.]+)')),
    ('Opera', re.compile(r'OPR/([\d.]+)')),
    ('Samsung Internet', re.compile(r'SamsungBrowser/([\d.]+)')),
    ('Vivaldi', re.compile(r'Vivaldi/([\d.]+)')),
    ('Brave', re.compile(r'Brave/([\d.]+)')),
    ('Chrome', re.compile(r'(?:Chrome|CriOS)/([\d.]+)')),
    ('Firefox', re.compile(r'(?:Firefox|FxiOS)/([\d.]+)')),
    ('Safari', re.compile(r'Version/([\d.]+).*Safari')),
    ('Internet Explorer', re.compile(r'(?:MSIE |rv:)([\d.]+).*Trident')),
)

_OS_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ('Android', re.compile(r'Android ([\d.]+)')),
    ('iOS', re.compile(r'(?:iPhone |CPU )OS ([\d_]+)')),
    ('iPadOS', re.compile(r'iPad.*OS ([\d_]+)')),
    ('Windows', re.compile(r'Windows NT ([\d.]+)')),
    ('macOS', re.compile(r'Mac OS X ([\d_.]+)')),
    ('Chrome OS', re.compile(r'CrOS \S+ ([\d.]+)')),
    ('Linux', re.compile(r'(Linux)')),
)

# Windows reports a kernel version; nobody thinks in those.
_WINDOWS_RELEASES = {
    '10.0': '10/11',
    '6.3': '8.1',
    '6.2': '8',
    '6.1': '7',
}

_MOBILE_HINT = re.compile(r'Mobi|Android|iPhone|iPod|Windows Phone', re.IGNORECASE)
_TABLET_HINT = re.compile(r'iPad|Tablet|PlayBook|Silk|(?=.*Android)(?!.*Mobi)', re.IGNORECASE)


@dataclass(frozen=True)
class ClientProfile:
    """What could be determined about the software making a request."""

    browser: str = ''
    browser_version: str = ''
    os: str = ''
    os_version: str = ''
    device_type: str = 'unknown'
    is_bot: bool = False
    bot_reason: str = ''


def parse(user_agent: str, client_hints: dict[str, str] | None = None) -> ClientProfile:
    """
    Identify the client from its user-agent string and any client hints.

    Client hints win wherever both are present, because they are declared by
    the browser rather than inferred from a string designed for compatibility
    rather than accuracy.
    """
    user_agent = (user_agent or '')[:MAX_UA_LENGTH]
    hints = client_hints or {}

    is_bot, bot_reason = detect_bot(user_agent)

    browser, browser_version = _match(_BROWSER_RULES, user_agent)
    os_name, os_version = _match(_OS_RULES, user_agent)
    os_version = os_version.replace('_', '.')
    if os_name == 'Windows':
        os_version = _WINDOWS_RELEASES.get(os_version, os_version)

    hinted_browser, hinted_version = _parse_sec_ch_ua(hints.get('brands', ''))
    if hinted_browser:
        browser, browser_version = hinted_browser, hinted_version or browser_version
    if hints.get('platform'):
        os_name = hints['platform']
        os_version = hints.get('platform_version') or os_version

    return ClientProfile(
        browser=browser,
        browser_version=browser_version,
        os=os_name,
        os_version=os_version,
        device_type=_device_type(user_agent, hints, is_bot),
        is_bot=is_bot,
        bot_reason=bot_reason,
    )


def detect_bot(user_agent: str) -> tuple[bool, str]:
    """
    Return whether the user agent self-identifies as automated, and which token said so.

    Only catches honest bots. Dishonest ones are caught later by the pipeline's
    behavioural scoring: a datacenter ASN, or zero engaged seconds with zero
    scroll, says more than any string can.
    """
    if not user_agent:
        # A browser always sends one. Nothing legitimate arrives without it.
        return True, 'missing user agent'

    lowered = user_agent.lower()
    for keyword in get_setting('BOT_UA_KEYWORDS'):
        if keyword in lowered:
            return True, f'ua contains {keyword!r}'
    return False, ''


def client_hints_from_meta(meta: dict) -> dict[str, str]:
    """Pull the Sec-CH-UA family out of ``request.META``."""
    return {
        'brands': _unquote(meta.get('HTTP_SEC_CH_UA', '')),
        'platform': _unquote(meta.get('HTTP_SEC_CH_UA_PLATFORM', '')),
        'platform_version': _unquote(meta.get('HTTP_SEC_CH_UA_PLATFORM_VERSION', '')),
        'mobile': _unquote(meta.get('HTTP_SEC_CH_UA_MOBILE', '')),
    }


def _parse_sec_ch_ua(brands: str) -> tuple[str, str]:
    """
    Pick the real browser out of a Sec-CH-UA brand list.

    The header deliberately includes a randomised fake brand — "Not_A Brand",
    "(Not(A:Brand" and similar — to stop servers hardcoding the list. It also
    includes the generic "Chromium" alongside the specific product. Both are
    skipped so the specific brand is what gets recorded.
    """
    if not brands:
        return '', ''

    fallback = ('', '')
    for entry in brands.split(','):
        match = re.match(r'\s*"?([^";]+)"?\s*;\s*v\s*=\s*"?([\d.]+)"?', entry)
        if not match:
            continue
        name, version = match.group(1).strip(), match.group(2)
        lowered = name.lower()
        if 'not' in lowered and 'brand' in lowered:
            continue
        if lowered == 'chromium':
            fallback = (name, version)
            continue
        return name, version
    return fallback


def _device_type(user_agent: str, hints: dict[str, str], is_bot: bool) -> str:
    if is_bot:
        return 'bot'
    if hints.get('mobile') == '?1':
        return 'mobile'
    if _TABLET_HINT.search(user_agent):
        return 'tablet'
    if _MOBILE_HINT.search(user_agent):
        return 'mobile'
    if user_agent:
        return 'desktop'
    return 'unknown'


def _match(rules: tuple[tuple[str, re.Pattern[str]], ...], text: str) -> tuple[str, str]:
    for label, pattern in rules:
        match = pattern.search(text)
        if match:
            version = match.group(1) if match.groups() else ''
            return label, ('' if version == label else version)
    return '', ''


def _unquote(value: str) -> str:
    """Structured-header strings arrive quoted; the quotes are not data."""
    return value.strip().strip('"')
