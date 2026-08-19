"""
Classification of where a session came from.

The rule is the one every analytics product uses, and the order matters:

1. An explicit ``utm_medium`` wins. Whoever built the link said what it was.
2. A paid click identifier (gclid / fbclid / msclkid) means paid, whatever the
   referrer claims.
3. Otherwise the referrer host decides, via the mapping below.
4. No referrer at all is "direct", which in practice also covers bookmarks,
   apps that strip the header, and anything arriving over HTTPS from HTTP.

The host mapping is intentionally a plain dict of suffixes rather than a
regex: adding a network is a one-line change, and suffix matching handles the
long tail of country domains (google.co.uk, google.com.au) without enumerating
them.
"""
from __future__ import annotations

from .models import Channel

# Suffix → channel. Matched against the referrer host from the right, so
# 'google.com' also covers 'www.google.com' and 'news.google.com'.
REFERRER_CHANNELS: dict[str, str] = {
    # Search
    'google.com': Channel.ORGANIC,
    'google.': Channel.ORGANIC,
    'bing.com': Channel.ORGANIC,
    'duckduckgo.com': Channel.ORGANIC,
    'search.yahoo.com': Channel.ORGANIC,
    'yandex.ru': Channel.ORGANIC,
    'baidu.com': Channel.ORGANIC,
    'ecosia.org': Channel.ORGANIC,
    'brave.com': Channel.ORGANIC,
    'startpage.com': Channel.ORGANIC,
    'qwant.com': Channel.ORGANIC,
    # Social
    'linkedin.com': Channel.SOCIAL,
    'lnkd.in': Channel.SOCIAL,
    'facebook.com': Channel.SOCIAL,
    'fb.com': Channel.SOCIAL,
    'instagram.com': Channel.SOCIAL,
    't.co': Channel.SOCIAL,
    'twitter.com': Channel.SOCIAL,
    'x.com': Channel.SOCIAL,
    'reddit.com': Channel.SOCIAL,
    'news.ycombinator.com': Channel.SOCIAL,
    'youtube.com': Channel.SOCIAL,
    'tiktok.com': Channel.SOCIAL,
    'threads.net': Channel.SOCIAL,
    'bsky.app': Channel.SOCIAL,
    'mastodon.social': Channel.SOCIAL,
    'whatsapp.com': Channel.SOCIAL,
    'telegram.org': Channel.SOCIAL,
    't.me': Channel.SOCIAL,
    'discord.com': Channel.SOCIAL,
    'medium.com': Channel.SOCIAL,
    'dev.to': Channel.SOCIAL,
    'github.com': Channel.SOCIAL,
    'stackoverflow.com': Channel.SOCIAL,
    # Email
    'mail.google.com': Channel.EMAIL,
    'outlook.com': Channel.EMAIL,
    'outlook.live.com': Channel.EMAIL,
    'mail.yahoo.com': Channel.EMAIL,
    'mail.proton.me': Channel.EMAIL,
}

PAID_MEDIUMS = frozenset({'cpc', 'ppc', 'paid', 'paidsearch', 'paid-search', 'cpm', 'display'})
SOCIAL_MEDIUMS = frozenset({'social', 'social-network', 'social-media', 'sm', 'paid-social'})
EMAIL_MEDIUMS = frozenset({'email', 'e-mail', 'newsletter', 'mail'})
ORGANIC_MEDIUMS = frozenset({'organic', 'search'})
REFERRAL_MEDIUMS = frozenset({'referral', 'link'})

CLICK_ID_PARAMS = ('gclid', 'fbclid', 'msclkid')


def classify(
    referrer_host: str,
    utm_medium: str = '',
    click_id: str | None = None,
    internal_hosts: frozenset[str] | tuple[str, ...] = (),
) -> str:
    """
    Return the :class:`~analytics.models.Channel` a session should be filed under.

    ``internal_hosts`` are this site's own hostnames; a referral from one of
    them is a visitor moving around the site, not an acquisition.
    """
    medium = (utm_medium or '').strip().lower()
    if medium:
        if medium in PAID_MEDIUMS:
            return Channel.PAID
        if medium in SOCIAL_MEDIUMS:
            return Channel.SOCIAL
        if medium in EMAIL_MEDIUMS:
            return Channel.EMAIL
        if medium in ORGANIC_MEDIUMS:
            return Channel.ORGANIC
        if medium in REFERRAL_MEDIUMS:
            return Channel.REFERRAL

    # A click identifier is only ever attached by an ad platform, so it
    # outranks a referrer that would otherwise read as organic or social.
    if click_id:
        return Channel.PAID

    host = (referrer_host or '').strip().lower()
    if not host:
        return Channel.DIRECT
    if host in internal_hosts:
        return Channel.INTERNAL

    mapped = _match_host(host)
    return mapped if mapped else Channel.REFERRAL


def extract_click_id(params: dict[str, str]) -> str | None:
    """Return the first recognised paid-click identifier, if any."""
    for name in CLICK_ID_PARAMS:
        value = params.get(name)
        if value:
            return value[:120]
    return None


def _match_host(host: str) -> str | None:
    if host in REFERRER_CHANNELS:
        return REFERRER_CHANNELS[host]

    for suffix, channel in REFERRER_CHANNELS.items():
        # 'google.' is a deliberate prefix-style entry covering every Google
        # country domain; everything else is a real domain suffix.
        if suffix.endswith('.'):
            if host.startswith(suffix) or f'.{suffix}' in f'.{host}':
                return channel
        elif host == suffix or host.endswith(f'.{suffix}'):
            return channel
    return None
