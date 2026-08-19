"""
Validation for the beacon ingest endpoint.

Everything arriving here is attacker-controlled: the endpoint is public,
unauthenticated and CSRF-exempt by necessity, because ``navigator.sendBeacon``
cannot attach a CSRF token or read a response. That makes the serializer the
only thing standing between the internet and the database, so it is strict by
default and rejects rather than coerces.

Four limits, each closing a specific hole:

* **batch size** — one request cannot enqueue unbounded work
* **event name allowlist** — a client cannot invent metric names, which would
  otherwise let anyone grow the ``name`` column's cardinality without bound
* **property payload size** — a single event cannot carry a megabyte of JSON
* **path allowlist** — reported paths must be the site's own routes or section
  anchors, so the ``path`` dimension cannot be poisoned with arbitrary strings
"""
from __future__ import annotations

import json
import time
from typing import Any

from rest_framework import serializers

from .defaults import get_setting
from .privacy import scrub, scrub_props

MAX_PATH_LENGTH = 200
MAX_TITLE_LENGTH = 200
MAX_NAME_LENGTH = 60
# Anything older than this is either a clock skew problem or a replay; either
# way the timestamp is not usable, so the server's own clock is substituted.
MAX_TIMESTAMP_AGE_SECONDS = 6 * 60 * 60
MAX_TIMESTAMP_SKEW_SECONDS = 5 * 60


class EventSerializer(serializers.Serializer):
    """One event inside a batch."""

    name = serializers.CharField(max_length=MAX_NAME_LENGTH)
    path = serializers.CharField(
        max_length=MAX_PATH_LENGTH, required=False, allow_blank=True, default=''
    )
    title = serializers.CharField(
        max_length=MAX_TITLE_LENGTH, required=False, allow_blank=True, default=''
    )
    # Client-side epoch seconds. Validated against the server clock below.
    t = serializers.FloatField(required=False, default=None, allow_null=True)
    props = serializers.DictField(required=False, default=dict)
    value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None
    )
    engaged_seconds = serializers.IntegerField(
        required=False, min_value=0, max_value=86_400, allow_null=True, default=None
    )
    max_scroll_depth = serializers.IntegerField(
        required=False, min_value=0, max_value=100, allow_null=True, default=None
    )
    is_spa_navigation = serializers.BooleanField(required=False, default=False)

    def validate_name(self, value: str) -> str:
        if value not in get_setting('EVENT_ALLOWLIST'):
            raise serializers.ValidationError(f'Unregistered event name: {value!r}')
        return value

    def validate_path(self, value: str) -> str:
        """
        Accept only paths this site actually serves.

        The SPA has a single route and navigates by anchor, so a valid path is
        '/' or '/#<section>' for a known section. Anything else is either a
        client bug or an attempt to write arbitrary strings into the dimension
        that the "top pages" report groups by.
        """
        if not value:
            return ''
        if not value.startswith('/'):
            raise serializers.ValidationError('Path must be site-relative.')

        if '#' in value:
            base, _, fragment = value.partition('#')
            if fragment not in get_setting('SECTION_ALLOWLIST'):
                raise serializers.ValidationError(f'Unknown section: {fragment!r}')
            return f'{base or "/"}#{fragment}'

        return value[:MAX_PATH_LENGTH]

    def validate_props(self, value: dict[str, Any]) -> dict[str, Any]:
        """Cap the payload size, then scrub anything credential-shaped out of it."""
        try:
            encoded = json.dumps(value, default=str)
        except (TypeError, ValueError):
            raise serializers.ValidationError('Properties must be JSON-serialisable.')

        limit = get_setting('INGEST_MAX_PROP_BYTES')
        if len(encoded.encode('utf-8')) > limit:
            raise serializers.ValidationError(f'Properties exceed {limit} bytes.')

        return scrub_props(value)

    def validate_t(self, value: float | None) -> float:
        """
        Trust the client's clock only within a narrow window.

        A browser clock can be wrong by years, and a replayed batch would
        otherwise let anyone write rows into an arbitrary date and corrupt the
        rollup. Out-of-range timestamps fall back to now.
        """
        now = time.time()
        if value is None:
            return now
        if value > now + MAX_TIMESTAMP_SKEW_SECONDS:
            return now
        if value < now - MAX_TIMESTAMP_AGE_SECONDS:
            return now
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get('name') == 'js_error':
            # Error text is the highest-risk free text the beacon sends: stack
            # traces routinely contain URLs with tokens in them.
            props = attrs.get('props') or {}
            for key in ('message', 'source', 'stack'):
                if key in props:
                    props[key] = scrub(str(props[key]), max_length=1_000)
            attrs['props'] = props
        return attrs


class EventBatchSerializer(serializers.Serializer):
    """The whole request body: a batch of events plus optional client context."""

    events = serializers.ListField(child=EventSerializer(), allow_empty=False)
    # Sent once per batch rather than per event, since it cannot change between
    # two events in the same flush.
    screen_width = serializers.IntegerField(required=False, min_value=0, max_value=32_767, default=None, allow_null=True)
    screen_height = serializers.IntegerField(required=False, min_value=0, max_value=32_767, default=None, allow_null=True)
    viewport_width = serializers.IntegerField(required=False, min_value=0, max_value=32_767, default=None, allow_null=True)
    viewport_height = serializers.IntegerField(required=False, min_value=0, max_value=32_767, default=None, allow_null=True)
    pixel_ratio = serializers.FloatField(required=False, min_value=0, max_value=10, default=None, allow_null=True)
    timezone = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    connection = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')

    def validate_events(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        limit = get_setting('INGEST_MAX_BATCH_SIZE')
        if len(value) > limit:
            raise serializers.ValidationError(f'At most {limit} events per batch.')
        return value
