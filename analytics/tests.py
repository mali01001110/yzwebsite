"""
Tests for the analytics app.

Uses ``django.test.TestCase`` rather than pytest, matching ``api/tests.py`` —
adding pytest-django would mean two test idioms in one repository for no
capability this suite needs.

Includes the eleven client-IP tests carried over from ``api/tests.py``, since
the module they cover moved here and the behaviour they assert is exactly the
behaviour that must not regress.
"""
from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from . import channels, consent, events, privacy, reports, security, useragent
from .admin import DailyStatAdmin, PageViewAdmin, VisitorAdmin, VisitorIPAdmin
from .buffer import KIND_PAGEVIEW, RecordBuffer, buffer, record
from .client_ip import get_client_ip, is_public_ip
from .defaults import get_setting
from .exports import (
    delete_ip_data,
    delete_visitor_data,
    export_ip_data,
    export_visitor_data,
)
from .models import (
    Channel,
    DailyStat,
    DeviceType,
    Event,
    PageView,
    SearchQuery,
    SecurityEvent,
    Session,
    Visitor,
    VisitorIP,
)
from .pipeline import (
    _initial_next_run,
    _run_due_jobs,
    enforce_retention,
    flush,
    rebuild_stats,
    rollup,
    sessionize,
)

INGEST_URL = '/api/analytics/events/'
# Reversed rather than spelled out: DJANGO_ADMIN_URL moves the admin, and a
# hardcoded '/admin/' would quietly stop pointing at it.
ADMIN_LOGIN_URL = reverse('admin:login')
VISITOR_IP_CHANGELIST_URL = reverse('admin:analytics_visitorip_changelist')
PUBLIC_IP = '93.184.216.34'
FORGED_IP = '8.8.8.8'
PROXY_IP = '10.0.0.1'
CLOUDFLARE_IP = '172.71.0.1'

CHROME_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
)
SAFARI_IOS_UA = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1'
)


class BufferIsolatedTestCase(TestCase):
    """Every test starts with an empty module-level buffer."""

    def setUp(self) -> None:
        super().setUp()
        buffer.clear()
        self.addCleanup(buffer.clear)


# ---------------------------------------------------------------------------
# Client IP resolution — carried over from api/tests.py
# ---------------------------------------------------------------------------

class ClientIpResolutionTests(TestCase):
    """The recorded address is only as trustworthy as this resolution step."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def _request(self, **headers):
        return self.factory.get('/', **headers)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_socket_peer_is_used_without_a_proxy(self):
        self.assertEqual(get_client_ip(self._request(REMOTE_ADDR=PUBLIC_IP)), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_forwarded_header_is_ignored_without_a_proxy(self):
        request = self._request(REMOTE_ADDR=PUBLIC_IP, HTTP_X_FORWARDED_FOR=FORGED_IP)
        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_client_is_read_from_behind_one_proxy(self):
        request = self._request(REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR=PUBLIC_IP)
        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_prepended_forgery_cannot_displace_the_real_address(self):
        request = self._request(
            REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR=f'{FORGED_IP}, 1.1.1.1, {PUBLIC_IP}'
        )
        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_hop_count_selects_the_right_entry(self):
        request = self._request(
            REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR=f'{FORGED_IP}, {PUBLIC_IP}, {PROXY_IP}'
        )
        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_short_chain_falls_back_to_the_socket_peer(self):
        request = self._request(REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR='')
        self.assertEqual(get_client_ip(request), PROXY_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_garbage_in_the_header_is_rejected(self):
        request = self._request(
            REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR="not-an-ip'; DROP TABLE--"
        )
        self.assertEqual(get_client_ip(request), PROXY_IP)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_unresolvable_address_is_none(self):
        self.assertIsNone(get_client_ip(self._request(REMOTE_ADDR='')))

    def test_public_and_private_ranges_are_distinguished(self):
        self.assertTrue(is_public_ip(PUBLIC_IP))
        for private in ('127.0.0.1', '10.0.0.4', '192.168.1.20', '::1'):
            self.assertFalse(is_public_ip(private), private)

    def test_reserved_ranges_do_not_count_as_public(self):
        for reserved in ('203.0.113.10', '198.51.100.7', '192.0.2.1'):
            self.assertFalse(is_public_ip(reserved), reserved)


class CloudflareHeaderTests(TestCase):
    """The new behaviour: a proxy-set header outranks X-Forwarded-For."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_cf_connecting_ip_wins(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR=CLOUDFLARE_IP,
            HTTP_CF_CONNECTING_IP=PUBLIC_IP,
            HTTP_X_FORWARDED_FOR=f'{FORGED_IP}, {PROXY_IP}',
        )
        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_malformed_cf_header_falls_through_to_the_chain(self):
        request = self.factory.get(
            '/', REMOTE_ADDR=PROXY_IP,
            HTTP_CF_CONNECTING_IP='garbage', HTTP_X_FORWARDED_FOR=PUBLIC_IP,
        )
        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1, ANALYTICS={'TRUSTED_IP_HEADERS': []})
    def test_header_list_is_configurable(self):
        """With the header removed from the setting, it must be ignored again."""
        request = self.factory.get(
            '/', REMOTE_ADDR=PROXY_IP,
            HTTP_CF_CONNECTING_IP=FORGED_IP, HTTP_X_FORWARDED_FOR=PUBLIC_IP,
        )
        self.assertEqual(get_client_ip(request), PUBLIC_IP)


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------

class SaltRotationTests(TestCase):
    """Stable within a rotation window, different across one."""

    def test_same_inputs_hash_identically_inside_a_window(self):
        first = privacy.hash_visitor(PUBLIC_IP, CHROME_UA)
        second = privacy.hash_visitor(PUBLIC_IP, CHROME_UA)
        self.assertEqual(first, second)

    def test_hash_changes_when_the_window_rolls_over(self):
        now = timezone.now()
        today = privacy.hash_visitor(PUBLIC_IP, CHROME_UA, now=now)
        tomorrow = privacy.hash_visitor(PUBLIC_IP, CHROME_UA, now=now + timedelta(days=1))
        self.assertNotEqual(today, tomorrow)

    def test_different_visitors_hash_differently(self):
        self.assertNotEqual(
            privacy.hash_visitor(PUBLIC_IP, CHROME_UA),
            privacy.hash_visitor(FORGED_IP, CHROME_UA),
        )

    def test_user_agent_is_part_of_the_identity(self):
        self.assertNotEqual(
            privacy.hash_visitor(PUBLIC_IP, CHROME_UA),
            privacy.hash_visitor(PUBLIC_IP, SAFARI_IOS_UA),
        )

    def test_hash_is_the_documented_length(self):
        self.assertEqual(len(privacy.hash_visitor(PUBLIC_IP, CHROME_UA)), 64)

    @override_settings(ANALYTICS={'SALT_ROTATION_HOURS': 1})
    def test_rotation_period_is_configurable(self):
        now = timezone.now()
        self.assertNotEqual(
            privacy.hash_visitor(PUBLIC_IP, CHROME_UA, now=now),
            privacy.hash_visitor(PUBLIC_IP, CHROME_UA, now=now + timedelta(hours=2)),
        )


class IpTruncationTests(TestCase):
    def test_ipv4_last_octet_is_zeroed(self):
        self.assertEqual(privacy.truncate_ip('93.184.216.34'), '93.184.216.0')

    def test_ipv6_keeps_only_the_routing_prefix(self):
        truncated = privacy.truncate_ip('2001:db8:1234:5678:9abc:def0:1234:5678')
        self.assertEqual(truncated, '2001:db8:1234::')

    def test_unparseable_address_is_none(self):
        for value in ('not-an-ip', '', None, '999.999.999.999'):
            self.assertIsNone(privacy.truncate_ip(value), value)

    def test_truncated_form_cannot_recover_the_original(self):
        self.assertNotEqual(privacy.truncate_ip('93.184.216.34'), '93.184.216.34')


class ScrubbingTests(TestCase):
    def test_email_addresses_are_removed(self):
        self.assertNotIn('ada@example.com', privacy.scrub('contact ada@example.com now'))

    def test_jwt_is_removed(self):
        token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        self.assertNotIn(token, privacy.scrub(f'Auth failed for {token}'))

    def test_bearer_token_is_removed(self):
        scrubbed = privacy.scrub('Authorization: Bearer sk_live_abcdef123456')
        self.assertNotIn('sk_live_abcdef123456', scrubbed)

    def test_ip_addresses_are_removed_from_free_text(self):
        self.assertNotIn('93.184.216.34', privacy.scrub('request from 93.184.216.34'))

    def test_ordinary_text_survives(self):
        self.assertIn('Cannot read property', privacy.scrub('Cannot read property of undefined'))

    def test_nested_props_are_scrubbed(self):
        scrubbed = privacy.scrub_props({'user': {'email': 'ada@example.com'}, 'count': 3})
        self.assertNotIn('ada@example.com', str(scrubbed))
        self.assertEqual(scrubbed['count'], 3)

    def test_recursion_depth_is_bounded(self):
        deep = current = {}
        for _ in range(20):
            current['next'] = {}
            current = current['next']
        privacy.scrub_props(deep)  # must not raise


class QueryStringTests(TestCase):
    def test_allowlisted_params_are_kept_in_the_clear(self):
        params = privacy.allowlisted_params('utm_source=linkedin&token=secret123')
        self.assertEqual(params, {'utm_source': 'linkedin'})

    def test_non_allowlisted_params_are_only_hashed(self):
        digest = privacy.hash_query_string('token=supersecretvalue')
        self.assertNotIn('supersecretvalue', digest)
        self.assertEqual(len(digest), 64)

    def test_allowlisted_only_query_produces_no_hash(self):
        self.assertEqual(privacy.hash_query_string('utm_source=linkedin'), '')

    def test_hash_is_order_independent(self):
        self.assertEqual(
            privacy.hash_query_string('a=1&b=2'), privacy.hash_query_string('b=2&a=1')
        )


class ReferrerTests(TestCase):
    def test_query_string_is_dropped_from_a_referrer(self):
        host, url = privacy.safe_referrer('https://example.com/page?token=abc')
        self.assertEqual(host, 'example.com')
        self.assertNotIn('token', url)

    def test_non_http_scheme_is_rejected(self):
        self.assertEqual(privacy.safe_referrer('javascript:alert(1)'), ('', ''))


# ---------------------------------------------------------------------------
# User agent and channels
# ---------------------------------------------------------------------------

class UserAgentTests(TestCase):
    def test_chrome_on_windows(self):
        profile = useragent.parse(CHROME_UA)
        self.assertEqual(profile.browser, 'Chrome')
        self.assertEqual(profile.os, 'Windows')
        self.assertEqual(profile.device_type, DeviceType.DESKTOP)
        self.assertFalse(profile.is_bot)

    def test_safari_on_iphone_is_mobile(self):
        profile = useragent.parse(SAFARI_IOS_UA)
        self.assertEqual(profile.browser, 'Safari')
        self.assertEqual(profile.device_type, DeviceType.MOBILE)

    def test_edge_is_not_reported_as_chrome(self):
        """Edge's UA contains 'Chrome', so rule order is what makes this pass."""
        edge = CHROME_UA.replace('Safari/537.36', 'Safari/537.36 Edg/130.0.0.0')
        self.assertEqual(useragent.parse(edge).browser, 'Edge')

    def test_client_hints_override_the_ua_string(self):
        profile = useragent.parse(
            CHROME_UA,
            {'brands': '"Not_A Brand";v="8", "Chromium";v="130", "Brave";v="130"',
             'platform': 'Linux', 'mobile': '?0'},
        )
        self.assertEqual(profile.browser, 'Brave')
        self.assertEqual(profile.os, 'Linux')

    def test_fake_brand_is_skipped(self):
        profile = useragent.parse(
            CHROME_UA, {'brands': '"(Not(A:Brand";v="8", "Chromium";v="130"'}
        )
        self.assertEqual(profile.browser, 'Chromium')

    def test_mobile_hint_wins_over_a_desktop_ua(self):
        profile = useragent.parse(CHROME_UA, {'mobile': '?1'})
        self.assertEqual(profile.device_type, DeviceType.MOBILE)

    def test_known_bots_are_flagged(self):
        for agent in ('Googlebot/2.1', 'curl/8.4.0', 'python-requests/2.31'):
            self.assertTrue(useragent.parse(agent).is_bot, agent)

    def test_missing_user_agent_is_a_bot(self):
        self.assertTrue(useragent.parse('').is_bot)


class ChannelClassificationTests(TestCase):
    def test_no_referrer_is_direct(self):
        self.assertEqual(channels.classify(''), Channel.DIRECT)

    def test_search_engine_is_organic(self):
        self.assertEqual(channels.classify('www.google.com'), Channel.ORGANIC)

    def test_google_country_domain_is_organic(self):
        self.assertEqual(channels.classify('google.co.uk'), Channel.ORGANIC)

    def test_linkedin_is_social(self):
        self.assertEqual(channels.classify('www.linkedin.com'), Channel.SOCIAL)

    def test_unknown_host_is_referral(self):
        self.assertEqual(channels.classify('some-blog.example'), Channel.REFERRAL)

    def test_utm_medium_outranks_the_referrer(self):
        self.assertEqual(channels.classify('google.com', utm_medium='cpc'), Channel.PAID)

    def test_click_id_forces_paid(self):
        self.assertEqual(channels.classify('google.com', click_id='abc123'), Channel.PAID)

    def test_own_host_is_internal(self):
        self.assertEqual(
            channels.classify('yannzakpa.space', internal_hosts=frozenset({'yannzakpa.space'})),
            Channel.INTERNAL,
        )

    def test_click_id_is_extracted_by_priority(self):
        self.assertEqual(channels.extract_click_id({'fbclid': 'x', 'gclid': 'y'}), 'y')


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

class ConsentTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': False})
    def test_tier_two_allowed_when_consent_not_required(self):
        self.assertTrue(consent.read(self.factory.get('/')).allows_tier_two)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': True})
    def test_tier_two_blocked_without_a_cookie(self):
        self.assertFalse(consent.read(self.factory.get('/')).allows_tier_two)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': True})
    def test_granting_cookie_allows_tier_two(self):
        request = self.factory.get('/')
        request.COOKIES['analytics.consent'] = 'essential:1,analytics:1'
        self.assertTrue(consent.read(request).allows_tier_two)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': True})
    def test_rejecting_cookie_blocks_tier_two(self):
        request = self.factory.get('/')
        request.COOKIES['analytics.consent'] = 'essential:1,analytics:0'
        self.assertFalse(consent.read(request).allows_tier_two)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': False, 'HONOR_DNT': True})
    def test_dnt_is_a_hard_opt_out_even_without_consent_gating(self):
        state = consent.read(self.factory.get('/', HTTP_DNT='1'))
        self.assertFalse(state.allows_tier_two)
        self.assertEqual(state.reason, 'dnt')

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': False, 'HONOR_DNT': True})
    def test_sec_gpc_is_a_hard_opt_out(self):
        self.assertFalse(consent.read(self.factory.get('/', HTTP_SEC_GPC='1')).allows_tier_two)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': True, 'HONOR_DNT': True})
    def test_dnt_overrides_a_granting_cookie(self):
        request = self.factory.get('/', HTTP_DNT='1')
        request.COOKIES['analytics.consent'] = 'essential:1,analytics:1'
        self.assertFalse(consent.read(request).allows_tier_two)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': False, 'HONOR_DNT': False})
    def test_dnt_can_be_ignored_by_setting(self):
        self.assertTrue(consent.read(self.factory.get('/', HTTP_DNT='1')).allows_tier_two)

    def test_malformed_cookie_grants_nothing(self):
        with override_settings(ANALYTICS={'REQUIRE_CONSENT': True}):
            request = self.factory.get('/')
            request.COOKIES['analytics.consent'] = '!!!garbage!!!'
            self.assertFalse(consent.read(request).allows_tier_two)


# ---------------------------------------------------------------------------
# Buffer and middleware
# ---------------------------------------------------------------------------

class BufferTests(TestCase):
    def test_drain_empties_the_buffer(self):
        target = RecordBuffer(hard_limit=10)
        target.append({'kind': 'x'})
        self.assertEqual(len(target.drain()), 1)
        self.assertEqual(len(target), 0)

    def test_hard_limit_discards_oldest_rather_than_growing(self):
        target = RecordBuffer(hard_limit=3)
        for index in range(10):
            target.append({'n': index})
        drained = target.drain()
        self.assertEqual(len(drained), 3)
        self.assertEqual(drained[0]['n'], 7)

    def test_drain_on_empty_buffer_is_cheap_and_safe(self):
        self.assertEqual(RecordBuffer(hard_limit=5).drain(), [])


@override_settings(TRUSTED_PROXY_COUNT=0)
class CollectorMiddlewareTests(BufferIsolatedTestCase):
    """Exercised through the real stack, so middleware order is covered too."""

    def test_page_view_is_buffered(self):
        self.client.get('/', REMOTE_ADDR=PUBLIC_IP, HTTP_USER_AGENT=CHROME_UA)
        records = buffer.drain()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['path'], '/')

    def test_nothing_is_written_to_the_database_during_the_request(self):
        """The hard requirement: no synchronous DB write in the request path."""
        self.client.get('/', REMOTE_ADDR=PUBLIC_IP, HTTP_USER_AGENT=CHROME_UA)
        self.assertEqual(Visitor.objects.count(), 0)
        self.assertEqual(PageView.objects.count(), 0)

    def test_raw_ip_never_reaches_a_model(self):
        self.client.get('/', REMOTE_ADDR=PUBLIC_IP, HTTP_USER_AGENT=CHROME_UA)
        flush()
        for session in Session.objects.all():
            self.assertNotEqual(session.ip_truncated, PUBLIC_IP)
            self.assertNotIn(PUBLIC_IP, session.ip_hash)

    def test_json_api_call_is_not_a_page_view(self):
        self.client.get('/api/hello/', REMOTE_ADDR=PUBLIC_IP)
        self.assertEqual(len(buffer.drain()), 0)

    def test_admin_browsing_is_excluded(self):
        self.client.get(ADMIN_LOGIN_URL, REMOTE_ADDR=PUBLIC_IP)
        self.assertEqual(len(buffer.drain()), 0)

    def test_static_asset_is_excluded(self):
        self.client.get('/static/analytics/beacon.js', REMOTE_ADDR=PUBLIC_IP)
        self.assertEqual(len(buffer.drain()), 0)

    def test_accept_ch_header_is_sent_on_html(self):
        response = self.client.get('/', REMOTE_ADDR=PUBLIC_IP)
        self.assertIn('Sec-CH-UA', response.headers.get('Accept-CH', ''))

    def test_spa_route_is_recorded(self):
        self.client.get('/projects', REMOTE_ADDR=PUBLIC_IP, HTTP_USER_AGENT=CHROME_UA)
        self.assertEqual(buffer.drain()[0]['path'], '/projects')

    @override_settings(ANALYTICS={'ENABLED': False})
    def test_disabling_the_app_collects_nothing(self):
        self.client.get('/', REMOTE_ADDR=PUBLIC_IP)
        self.assertEqual(len(buffer.drain()), 0)

    def test_collection_failure_does_not_break_the_response(self):
        with patch('analytics.middleware.record', side_effect=RuntimeError('boom')):
            response = self.client.get('/', REMOTE_ADDR=PUBLIC_IP)
        self.assertEqual(response.status_code, 200)


class MiddlewareLatencyTests(BufferIsolatedTestCase):
    """The added per-request cost has a stated budget, so it is measured."""

    def test_added_latency_is_under_one_millisecond(self):
        import time

        from .middleware import CollectorMiddleware

        factory = RequestFactory()
        request = factory.get('/', REMOTE_ADDR=PUBLIC_IP, HTTP_USER_AGENT=CHROME_UA)
        request.analytics_consent = consent.ConsentState(analytics=True)

        from django.http import HttpResponse

        def view(_request):
            return HttpResponse('<html></html>', content_type='text/html')

        middleware = CollectorMiddleware(view)

        iterations = 200
        started = time.perf_counter()
        for _ in range(iterations):
            middleware(request)
        elapsed_ms = (time.perf_counter() - started) * 1000 / iterations

        buffer.clear()
        self.assertLess(
            elapsed_ms, 1.0, f'Collector added {elapsed_ms:.3f} ms per request'
        )


# ---------------------------------------------------------------------------
# Ingest endpoint
# ---------------------------------------------------------------------------

@override_settings(TRUSTED_PROXY_COUNT=0)
class IngestEndpointTests(BufferIsolatedTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()

    def _post(self, payload, **extra):
        return self.client.post(INGEST_URL, payload, format='json', **extra)

    def test_valid_batch_returns_204_with_no_body(self):
        response = self._post({'events': [{'name': 'pageview', 'path': '/'}]})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(response.content)

    def test_events_are_buffered_not_written(self):
        self._post({'events': [{'name': 'pageview', 'path': '/'}]})
        self.assertEqual(PageView.objects.count(), 0)
        self.assertEqual(len(buffer.drain()), 1)

    def test_unregistered_event_name_is_rejected(self):
        response = self._post({'events': [{'name': 'definitely_not_registered'}]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_section_is_rejected(self):
        response = self._post({'events': [{'name': 'section_view', 'path': '/#nope'}]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_known_section_is_accepted(self):
        response = self._post({'events': [{'name': 'section_view', 'path': '/#skills'}]})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_absolute_path_is_rejected(self):
        response = self._post({'events': [{'name': 'pageview', 'path': 'https://evil.example/x'}]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_batch_is_rejected(self):
        self.assertEqual(
            self._post({'events': []}).status_code, status.HTTP_400_BAD_REQUEST
        )

    @override_settings(ANALYTICS={'INGEST_MAX_BATCH_SIZE': 3})
    def test_oversized_batch_is_rejected(self):
        payload = {'events': [{'name': 'pageview'} for _ in range(4)]}
        self.assertEqual(self._post(payload).status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(ANALYTICS={'INGEST_MAX_PROP_BYTES': 100})
    def test_oversized_props_are_rejected(self):
        payload = {'events': [{'name': 'pageview', 'props': {'blob': 'x' * 500}}]}
        self.assertEqual(self._post(payload).status_code, status.HTTP_400_BAD_REQUEST)

    def test_foreign_origin_is_refused(self):
        response = self._post(
            {'events': [{'name': 'pageview'}]}, HTTP_ORIGIN='https://evil.example'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allowed_origin_is_accepted(self):
        response = self._post(
            {'events': [{'name': 'pageview'}]}, HTTP_ORIGIN='http://localhost:5173'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_get_is_not_allowed(self):
        self.assertEqual(
            self.client.get(INGEST_URL).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_future_timestamp_is_clamped_to_now(self):
        import time as time_module

        far_future = time_module.time() + 86_400
        self._post({'events': [{'name': 'pageview', 't': far_future}]})
        self.assertLess(buffer.drain()[0]['occurred_at'], far_future)

    def test_js_error_props_are_scrubbed(self):
        self._post({'events': [{
            'name': 'js_error',
            'props': {'message': 'failed for ada@example.com'},
        }]})
        self.assertNotIn('ada@example.com', str(buffer.drain()[0]['props']))

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': True})
    def test_consent_gating_discards_silently(self):
        response = self._post({'events': [{'name': 'pageview'}]})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(buffer.drain()), 0)

    @override_settings(ANALYTICS={'REQUIRE_CONSENT': True})
    def test_consent_cookie_permits_collection(self):
        self.client.cookies['analytics.consent'] = 'essential:1,analytics:1'
        self._post({'events': [{'name': 'pageview'}]})
        self.assertEqual(len(buffer.drain()), 1)

    @override_settings(ANALYTICS={'HONOR_DNT': True, 'REQUIRE_CONSENT': False})
    def test_dnt_blocks_ingest(self):
        self._post({'events': [{'name': 'pageview'}]}, HTTP_DNT='1')
        self.assertEqual(len(buffer.drain()), 0)


class IngestThrottleTests(BufferIsolatedTestCase):
    """Throttling is the only defence on a public, unauthenticated endpoint."""

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)

    @override_settings(ANALYTICS={'INGEST_THROTTLE_RATE': '2/hour'})
    def test_requests_over_the_rate_are_rejected(self):
        payload = {'events': [{'name': 'pageview'}]}
        for _ in range(2):
            self.assertEqual(
                self.client.post(INGEST_URL, payload, format='json').status_code,
                status.HTTP_204_NO_CONTENT,
            )
        self.assertEqual(
            self.client.post(INGEST_URL, payload, format='json').status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @override_settings(ANALYTICS={'INGEST_THROTTLE_RATE': '1/hour'})
    def test_throttle_hit_is_recorded_as_a_security_event(self):
        payload = {'events': [{'name': 'pageview'}]}
        self.client.post(INGEST_URL, payload, format='json')
        buffer.clear()
        self.client.post(INGEST_URL, payload, format='json')

        kinds = [item.get('event_kind') for item in buffer.drain()]
        self.assertIn('rate_limit', kinds)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@override_settings(TRUSTED_PROXY_COUNT=0)
class FlushTests(BufferIsolatedTestCase):
    def _buffer_pageview(self, path='/', visitor='v1', **overrides):
        payload = {
            'visitor_id': privacy.hash_visitor(f'{visitor}.1.1.1', CHROME_UA),
            'ip_hash': 'hash',
            'ip_address': PUBLIC_IP,
            'user_agent': CHROME_UA,
            'client_hints': {},
            'path': path,
            'query_hash': '',
            'params': {},
            'referrer_host': '',
            'referrer_url': '',
            'country_hint': 'CI',
            'language': 'en-US',
            'status_code': 200,
            'response_ms': 12,
            'user_id': None,
            'occurred_at': timezone.now().timestamp(),
            'is_spa_navigation': False,
        }
        payload.update(overrides)
        record(KIND_PAGEVIEW, **payload)

    def test_flush_creates_visitor_session_and_pageview(self):
        self._buffer_pageview()
        self.assertEqual(flush(), 1)
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(PageView.objects.count(), 1)

    def test_empty_buffer_flushes_nothing(self):
        self.assertEqual(flush(), 0)

    def test_repeat_visitor_reuses_one_session(self):
        self._buffer_pageview(path='/')
        self._buffer_pageview(path='/#skills')
        flush()
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(PageView.objects.count(), 2)

    def test_distinct_visitors_get_distinct_sessions(self):
        self._buffer_pageview(visitor='a')
        self._buffer_pageview(visitor='b')
        flush()
        self.assertEqual(Visitor.objects.count(), 2)
        self.assertEqual(Session.objects.count(), 2)

    def test_country_comes_from_the_cloudflare_hint(self):
        self._buffer_pageview()
        flush()
        self.assertEqual(Session.objects.get().country, 'CI')

    def test_user_agent_is_parsed_in_the_worker(self):
        self._buffer_pageview()
        flush()
        session = Session.objects.get()
        self.assertEqual(session.browser, 'Chrome')
        self.assertEqual(session.os, 'Windows')

    def test_first_touch_attribution_is_written_once(self):
        self._buffer_pageview(referrer_host='www.google.com')
        flush()
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.first_touch_channel, Channel.ORGANIC)
        self.assertEqual(visitor.last_touch_channel, Channel.ORGANIC)

    def test_flush_is_atomic_on_failure(self):
        self._buffer_pageview()
        with patch('analytics.pipeline.PageView.objects.bulk_create',
                   side_effect=RuntimeError('boom')):
            self.assertEqual(flush(), 0)
        self.assertEqual(PageView.objects.count(), 0)
        self.assertEqual(Visitor.objects.count(), 0)


class SessionizationTests(TestCase):
    def _session(self, started_at, pageview_times=()):
        visitor = Visitor.objects.create(
            visitor_id=f'v{timezone.now().timestamp()}{len(pageview_times)}'[:64],
            first_seen_at=started_at,
            last_seen_at=started_at,
        )
        session = Session.objects.create(visitor=visitor, started_at=started_at)
        for index, moment in enumerate(pageview_times):
            PageView.objects.create(
                session=session, path=f'/#p{index}', occurred_at=moment, engaged_seconds=20
            )
        return session

    def test_idle_session_is_closed(self):
        old = timezone.now() - timedelta(hours=2)
        self._session(old, [old])
        self.assertEqual(sessionize(), 1)
        self.assertIsNotNone(Session.objects.get().ended_at)

    def test_active_session_is_left_open(self):
        now = timezone.now()
        self._session(now, [now])
        self.assertEqual(sessionize(), 0)
        self.assertIsNone(Session.objects.get().ended_at)

    def test_closing_computes_pageview_count_and_exit_path(self):
        base = timezone.now() - timedelta(hours=3)
        self._session(base, [base, base + timedelta(minutes=1), base + timedelta(minutes=2)])
        sessionize()
        session = Session.objects.get()
        self.assertEqual(session.pageview_count, 3)
        self.assertEqual(session.exit_path, '/#p2')

    def test_single_pageview_with_no_engagement_is_a_bounce(self):
        old = timezone.now() - timedelta(hours=2)
        session = self._session(old)
        PageView.objects.create(session=session, path='/', occurred_at=old, engaged_seconds=0)
        sessionize()
        self.assertTrue(Session.objects.get().is_bounce)

    def test_engaged_single_pageview_is_not_a_bounce(self):
        old = timezone.now() - timedelta(hours=2)
        session = self._session(old)
        PageView.objects.create(session=session, path='/', occurred_at=old, engaged_seconds=120)
        sessionize()
        self.assertFalse(Session.objects.get().is_bounce)

    def test_session_with_no_pageviews_still_closes(self):
        self._session(timezone.now() - timedelta(hours=2))
        self.assertEqual(sessionize(), 1)

    def test_sessionize_is_idempotent(self):
        old = timezone.now() - timedelta(hours=2)
        self._session(old, [old])
        self.assertEqual(sessionize(), 1)
        self.assertEqual(sessionize(), 0)

    def test_duration_uses_engaged_time_not_wall_clock(self):
        base = timezone.now() - timedelta(hours=4)
        self._session(base, [base, base + timedelta(hours=1)])
        sessionize()
        # Two pageviews at 20 engaged seconds each, across an hour of wall clock.
        self.assertEqual(Session.objects.get().duration_seconds, 40)


class RollupTests(TestCase):
    def setUp(self) -> None:
        self.today = timezone.now().date()
        moment = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        self.visitor = Visitor.objects.create(
            visitor_id='rollup-visitor', first_seen_at=moment, last_seen_at=moment
        )
        self.session = Session.objects.create(
            visitor=self.visitor,
            started_at=moment,
            landing_path='/',
            country='CI',
            device_type=DeviceType.DESKTOP,
            channel=Channel.ORGANIC,
            is_bounce=False,
        )
        for path in ('/', '/#skills', '/#skills'):
            PageView.objects.create(
                session=self.session, path=path, occurred_at=moment, engaged_seconds=30
            )

    def test_site_wide_row_totals_the_day(self):
        rollup(self.today)
        row = DailyStat.objects.get(
            date=self.today, path__isnull=True, country__isnull=True,
            device_type__isnull=True, channel__isnull=True,
        )
        self.assertEqual(row.pageviews, 3)
        self.assertEqual(row.unique_visitors, 1)
        self.assertEqual(row.sessions, 1)
        self.assertEqual(row.total_engaged_seconds, 90)

    def test_per_path_rows_are_written(self):
        rollup(self.today)
        row = DailyStat.objects.get(
            date=self.today, path='/#skills', country__isnull=True,
            device_type__isnull=True, channel__isnull=True,
        )
        self.assertEqual(row.pageviews, 2)

    def test_rollup_is_idempotent(self):
        first = rollup(self.today)
        count_after_first = DailyStat.objects.count()
        second = rollup(self.today)
        self.assertEqual(first, second)
        self.assertEqual(DailyStat.objects.count(), count_after_first)

    def test_rerunning_does_not_double_the_counts(self):
        rollup(self.today)
        rollup(self.today)
        row = DailyStat.objects.get(
            date=self.today, path__isnull=True, country__isnull=True,
            device_type__isnull=True, channel__isnull=True,
        )
        self.assertEqual(row.pageviews, 3)

    def test_bot_traffic_is_excluded(self):
        Session.objects.update(is_bot=True)
        rollup(self.today)
        self.assertEqual(DailyStat.objects.count(), 0)

    def test_rebuild_covers_a_range(self):
        rebuild_stats(self.today - timedelta(days=2), self.today)
        self.assertTrue(DailyStat.objects.filter(date=self.today).exists())

    def test_country_breakdown_row_exists(self):
        rollup(self.today)
        self.assertTrue(
            DailyStat.objects.filter(
                date=self.today, country='CI', path__isnull=True,
                device_type__isnull=True, channel__isnull=True,
            ).exists()
        )


class RetentionTests(TestCase):
    def setUp(self) -> None:
        self.old = timezone.now() - timedelta(days=200)
        self.recent = timezone.now() - timedelta(days=1)
        self.visitor = Visitor.objects.create(
            visitor_id='retention-visitor', first_seen_at=self.old, last_seen_at=self.recent
        )
        self.session = Session.objects.create(
            visitor=self.visitor, started_at=self.old,
            ip_truncated='93.184.216.0', latitude='5.34', longitude='-4.02', city='Abidjan',
        )
        PageView.objects.create(session=self.session, path='/', occurred_at=self.old)
        PageView.objects.create(session=self.session, path='/', occurred_at=self.recent)

    def test_expired_pageviews_are_deleted(self):
        enforce_retention()
        self.assertEqual(PageView.objects.count(), 1)

    def test_recent_pageviews_survive(self):
        enforce_retention()
        self.assertTrue(PageView.objects.filter(occurred_at=self.recent).exists())

    def test_location_data_is_cleared_on_older_sessions(self):
        enforce_retention()
        session = Session.objects.get()
        self.assertIsNone(session.ip_truncated)
        self.assertIsNone(session.latitude)
        self.assertEqual(session.city, '')

    def test_rollups_are_never_deleted(self):
        DailyStat.objects.create(date=self.old.date(), pageviews=5)
        enforce_retention()
        self.assertEqual(DailyStat.objects.count(), 1)

    def test_retention_is_idempotent(self):
        enforce_retention()
        remaining = PageView.objects.count()
        enforce_retention()
        self.assertEqual(PageView.objects.count(), remaining)


class SchedulerTests(TestCase):
    """
    The periodic jobs must not depend on the process outliving their interval.

    Seeding the schedule one interval ahead meant the hourly rollup never ran
    under the autoreloader or across a platform restart, so the dashboard —
    which reads DailyStat and never the raw tables — stayed empty while
    collection itself was working fine.
    """

    def setUp(self) -> None:
        self.patches = {
            name: patch(f'analytics.pipeline.{name}')
            for name in ('sessionize', 'rollup_recent', 'enforce_retention', '_ensure_partitions')
        }
        self.jobs = {name: p.start() for name, p in self.patches.items()}
        self.addCleanup(lambda: [p.stop() for p in self.patches.values()])

    def test_every_job_runs_on_the_first_tick(self):
        next_run = _initial_next_run()
        _run_due_jobs(next_run, time.monotonic())

        for name, job in self.jobs.items():
            with self.subTest(job=name):
                job.assert_called_once()

    def test_jobs_do_not_rerun_before_their_interval(self):
        next_run = _initial_next_run()
        now = time.monotonic()
        _run_due_jobs(next_run, now)
        _run_due_jobs(next_run, now + 1)

        for name, job in self.jobs.items():
            with self.subTest(job=name):
                self.assertEqual(job.call_count, 1)

    def test_each_job_reruns_only_once_its_own_interval_elapses(self):
        next_run = _initial_next_run()
        now = time.monotonic()
        _run_due_jobs(next_run, now)

        # Past the hourly rollup but well short of the daily retention sweep.
        _run_due_jobs(next_run, now + get_setting('ROLLUP_INTERVAL_SECONDS') + 1)

        self.assertEqual(self.jobs['rollup_recent'].call_count, 2)
        self.assertEqual(self.jobs['sessionize'].call_count, 2)
        self.assertEqual(self.jobs['enforce_retention'].call_count, 1)

    def test_a_failing_job_does_not_stop_the_others(self):
        self.jobs['sessionize'].side_effect = RuntimeError('boom')
        _run_due_jobs(_initial_next_run(), time.monotonic())

        self.jobs['rollup_recent'].assert_called_once()
        self.jobs['enforce_retention'].assert_called_once()


# ---------------------------------------------------------------------------
# Events, experiments, security
# ---------------------------------------------------------------------------

class TrackEventTests(BufferIsolatedTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()

    def test_allowlisted_event_is_buffered(self):
        request = self.factory.get('/', REMOTE_ADDR=PUBLIC_IP)
        self.assertTrue(events.track_event(request, 'contact_submitted'))
        self.assertEqual(len(buffer.drain()), 1)

    def test_unregistered_event_is_refused(self):
        request = self.factory.get('/', REMOTE_ADDR=PUBLIC_IP)
        self.assertFalse(events.track_event(request, 'not_a_real_event'))
        self.assertEqual(len(buffer.drain()), 0)

    def test_props_are_scrubbed_before_buffering(self):
        request = self.factory.get('/', REMOTE_ADDR=PUBLIC_IP)
        events.track_event(request, 'form_submit', props={'email': 'ada@example.com'})
        self.assertNotIn('ada@example.com', str(buffer.drain()[0]['props']))


class ContactConversionTests(BufferIsolatedTestCase):
    """The site's only real conversion is wired end to end."""

    def test_contact_submission_emits_an_event(self):
        APIClient().post(
            '/api/contact/',
            {'name': 'Ada', 'email': 'ada@example.com', 'message': 'Hello there'},
            format='json',
        )
        names = [item.get('name') for item in buffer.drain()]
        self.assertIn('contact_submitted', names)


class ExperimentAssignmentTests(TestCase):
    def test_assignment_is_stable_for_one_visitor(self):
        first = events.assign_variant('visitor-a', 'hero-copy')
        second = events.assign_variant('visitor-a', 'hero-copy')
        self.assertEqual(first, second)

    def test_assignment_differs_across_experiments(self):
        variants = [f'v{index}' for index in range(8)]
        a = events.assign_variant('visitor-a', 'experiment-one', variants)
        b = events.assign_variant('visitor-a', 'experiment-two', variants)
        self.assertNotEqual(a, b)

    def test_assignment_is_one_of_the_offered_variants(self):
        self.assertIn(
            events.assign_variant('visitor-a', 'k', ('control', 'treatment')),
            ('control', 'treatment'),
        )

    def test_split_is_roughly_even(self):
        counts = {'control': 0, 'treatment': 0}
        for index in range(2_000):
            counts[events.assign_variant(f'visitor-{index}', 'split-test')] += 1
        self.assertGreater(min(counts.values()) / 2_000, 0.45)

    def test_empty_variant_list_is_rejected(self):
        with self.assertRaises(ValueError):
            events.assign_variant('v', 'k', ())


@override_settings(TRUSTED_PROXY_COUNT=0)
class SecurityDetectionTests(BufferIsolatedTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()
        security.tracker.reset()
        self.addCleanup(security.tracker.reset)

    def test_scan_pattern_is_detected(self):
        self.assertEqual(security.matched_scan_pattern('/wp-admin/setup.php'), 'wp-admin')

    def test_env_file_probe_is_detected(self):
        self.assertIsNotNone(security.matched_scan_pattern('/.env'))

    def test_ordinary_path_is_not_a_scan(self):
        self.assertIsNone(security.matched_scan_pattern('/#skills'))

    def test_scan_is_buffered_as_a_security_event(self):
        request = self.factory.get('/wp-login.php', REMOTE_ADDR=PUBLIC_IP)
        security.observe_rejected_request(request, 404)
        records = buffer.drain()
        self.assertEqual(records[0]['kind'], 'security')
        self.assertEqual(records[0]['event_kind'], 'path_scan')

    def test_repeat_scans_are_counted(self):
        for _ in range(6):
            security.observe_rejected_request(
                self.factory.get('/wp-admin/', REMOTE_ADDR=PUBLIC_IP), 404
            )
        records = buffer.drain()
        self.assertTrue(records[-1]['metadata']['is_repeat_offender'])

    def test_enumeration_is_detected_after_the_threshold(self):
        for index in range(20):
            security.observe_rejected_request(
                self.factory.get(f'/projects/{index}/', REMOTE_ADDR=PUBLIC_IP), 404
            )
        kinds = [item['metadata'].get('hits_in_window') for item in buffer.drain()]
        self.assertTrue(any(kinds))

    def test_a_few_missing_pages_are_not_enumeration(self):
        for index in range(3):
            security.observe_rejected_request(
                self.factory.get(f'/projects/{index}/', REMOTE_ADDR=PUBLIC_IP), 404
            )
        self.assertEqual(len(buffer.drain()), 0)

    def test_failed_login_is_recorded(self):
        security.record_failed_login(self.factory.post(ADMIN_LOGIN_URL), 'admin')
        self.assertEqual(len(buffer.drain()), 1)

    def test_failed_login_username_is_scrubbed(self):
        security.record_failed_login(self.factory.post(ADMIN_LOGIN_URL), 'ada@example.com')
        self.assertNotIn('ada@example.com', buffer.drain()[0]['username_attempted'])

    def test_security_events_persist_through_flush(self):
        security.record_failed_login(self.factory.post(ADMIN_LOGIN_URL), 'root')
        flush()
        self.assertEqual(SecurityEvent.objects.count(), 1)
        self.assertEqual(SecurityEvent.objects.get().username_attempted, 'root')

    def test_no_raw_ip_in_a_security_event(self):
        security.record_failed_login(
            self.factory.post(ADMIN_LOGIN_URL, REMOTE_ADDR=PUBLIC_IP), 'root'
        )
        flush()
        self.assertNotEqual(SecurityEvent.objects.get().ip_truncated, PUBLIC_IP)


class LoginSignalTests(BufferIsolatedTestCase):
    """The user_logged_in handler is the only place identity is stitched."""

    def test_login_attaches_the_visitor_to_the_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user('owner', password='not-a-real-password-1')

        factory = RequestFactory()
        request = factory.get('/', REMOTE_ADDR=PUBLIC_IP, HTTP_USER_AGENT=CHROME_UA)
        visitor_id = events.visitor_id_for(request)
        Visitor.objects.create(
            visitor_id=visitor_id, first_seen_at=timezone.now(), last_seen_at=timezone.now()
        )

        from django.contrib.auth.signals import user_logged_in

        user_logged_in.send(sender=user_model, request=request, user=user)

        self.assertEqual(Visitor.objects.get(visitor_id=visitor_id).user, user)


# ---------------------------------------------------------------------------
# Reports, admin, exports
# ---------------------------------------------------------------------------

class ReportTests(TestCase):
    def setUp(self) -> None:
        self.today = timezone.now().date()
        DailyStat.objects.create(
            date=self.today, pageviews=100, unique_visitors=40, sessions=50,
            bounces=20, total_engaged_seconds=3_000,
        )
        DailyStat.objects.create(
            date=self.today, path='/#skills', pageviews=30, unique_visitors=12, sessions=15,
        )
        DailyStat.objects.create(
            date=self.today, country='CI', pageviews=60, unique_visitors=25, sessions=30,
        )

    def test_summary_reads_only_site_wide_rows(self):
        summary = reports.summary(self.today, self.today)
        self.assertEqual(summary['pageviews'], 100)
        self.assertEqual(summary['sessions'], 50)
        self.assertEqual(summary['bounce_rate'], 40.0)

    def test_time_series_fills_days_with_no_data(self):
        series = reports.time_series(self.today - timedelta(days=4), self.today)
        self.assertEqual(len(series), 5)
        self.assertEqual(series[0]['pageviews'], 0)
        self.assertEqual(series[-1]['pageviews'], 100)

    def test_path_breakdown_returns_only_path_rows(self):
        rows = reports.breakdown(self.today, self.today, 'path')
        self.assertEqual([row['value'] for row in rows], ['/#skills'])

    def test_country_breakdown_returns_only_country_rows(self):
        rows = reports.breakdown(self.today, self.today, 'country')
        self.assertEqual([row['value'] for row in rows], ['CI'])

    def test_summary_of_an_empty_period_is_zeroed_not_an_error(self):
        summary = reports.summary(self.today - timedelta(days=90), self.today - timedelta(days=80))
        self.assertEqual(summary['pageviews'], 0)
        self.assertEqual(summary['bounce_rate'], 0.0)

    def test_percentile_of_an_empty_sample_is_zero(self):
        self.assertEqual(reports._percentile([], 75), 0.0)

    def test_percentile_picks_the_nearest_rank(self):
        self.assertEqual(reports._percentile([1, 2, 3, 4], 75), 3)


class DashboardQueryCountTests(TestCase):
    """
    Guards against N+1 in the dashboard.

    assertNumQueries rather than django-debug-toolbar: this enforces the budget
    on every future change instead of reporting it once.
    """

    def setUp(self) -> None:
        today = timezone.now().date()
        for index in range(30):
            DailyStat.objects.create(
                date=today - timedelta(days=index), pageviews=10, unique_visitors=5, sessions=6
            )

    def test_summary_is_one_query(self):
        start, end = reports.date_range(30)
        with self.assertNumQueries(1):
            reports.summary(start, end)

    def test_time_series_is_one_query(self):
        start, end = reports.date_range(30)
        with self.assertNumQueries(1):
            reports.time_series(start, end)

    def test_each_breakdown_is_one_query(self):
        start, end = reports.date_range(30)
        for dimension in ('path', 'country', 'device_type', 'channel'):
            with self.assertNumQueries(1):
                reports.breakdown(start, end, dimension)


class AdminTests(TestCase):
    def setUp(self) -> None:
        self.user_model = get_user_model()
        self.superuser = self.user_model.objects.create_superuser(
            'owner', 'owner@example.com', 'not-a-real-password-1'
        )
        self.client.force_login(self.superuser)

    def test_every_model_is_registered(self):
        for model in (Visitor, Session, PageView, Event, SecurityEvent,
                      SearchQuery, DailyStat):
            self.assertIn(model, admin.site._registry, model.__name__)

    def test_models_cannot_be_added_or_changed(self):
        model_admin = VisitorAdmin(Visitor, admin.site)
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))

    def test_deletion_requires_a_superuser(self):
        model_admin = PageViewAdmin(PageView, admin.site)

        class FakeRequest:
            user = self.user_model(is_superuser=False)

        self.assertFalse(model_admin.has_delete_permission(FakeRequest()))

    def test_superuser_may_delete(self):
        model_admin = PageViewAdmin(PageView, admin.site)

        class FakeRequest:
            user = self.user_model(is_superuser=True)

        self.assertTrue(model_admin.has_delete_permission(FakeRequest()))

    def test_all_fields_are_read_only(self):
        model_admin = VisitorAdmin(Visitor, admin.site)
        readonly = model_admin.get_readonly_fields(None)
        for field in ('visitor_id', 'first_seen_at', 'last_seen_at', 'is_bot'):
            self.assertIn(field, readonly)

    def test_dashboard_renders(self):
        response = self.client.get(reverse('admin:analytics_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visitor analytics')

    def test_dashboard_data_returns_json(self):
        response = self.client.get(reverse('admin:analytics_dashboard_data'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ('summary', 'series', 'top_paths', 'countries', 'live'):
            self.assertIn(key, payload)

    def test_dashboard_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse('admin:analytics_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(ADMIN_LOGIN_URL, response['Location'])

    def test_days_parameter_is_clamped(self):
        response = self.client.get(reverse('admin:analytics_dashboard_data'), {'days': '99999'})
        self.assertEqual(response.json()['range']['days'], 365)

    def test_malformed_days_parameter_falls_back(self):
        response = self.client.get(reverse('admin:analytics_dashboard_data'), {'days': 'abc'})
        self.assertEqual(response.json()['range']['days'], 30)

    def test_csv_export_produces_a_download(self):
        model_admin = DailyStatAdmin(DailyStat, admin.site)
        DailyStat.objects.create(date=timezone.now().date(), pageviews=1)
        response = model_admin.export_as_csv(None, DailyStat.objects.all())
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment;', response['Content-Disposition'])


class DataSubjectRequestTests(TestCase):
    def setUp(self) -> None:
        moment = timezone.now()
        self.visitor = Visitor.objects.create(
            visitor_id='subject-visitor', first_seen_at=moment, last_seen_at=moment
        )
        session = Session.objects.create(visitor=self.visitor, started_at=moment)
        PageView.objects.create(session=session, path='/', occurred_at=moment)
        Event.objects.create(session=session, name='pageview', occurred_at=moment)

    def test_export_returns_the_visitor_and_its_rows(self):
        payload = export_visitor_data('subject-visitor')
        self.assertEqual(payload['visitor']['visitor_id'], 'subject-visitor')
        self.assertEqual(len(payload['sessions']), 1)
        self.assertEqual(len(payload['sessions'][0]['pageviews']), 1)

    def test_export_of_an_unknown_visitor_is_empty_not_an_error(self):
        payload = export_visitor_data('does-not-exist')
        self.assertIsNone(payload['visitor'])

    def test_export_contains_no_raw_ip(self):
        payload = export_visitor_data('subject-visitor')
        self.assertNotIn('ip_address', payload['sessions'][0])

    def test_delete_removes_everything_for_the_visitor(self):
        delete_visitor_data('subject-visitor')
        self.assertEqual(Visitor.objects.count(), 0)
        self.assertEqual(Session.objects.count(), 0)
        self.assertEqual(PageView.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 0)

    def test_delete_leaves_rollups_alone(self):
        DailyStat.objects.create(date=timezone.now().date(), pageviews=10)
        delete_visitor_data('subject-visitor')
        self.assertEqual(DailyStat.objects.count(), 1)

    def test_delete_of_an_unknown_visitor_is_a_no_op(self):
        self.assertEqual(delete_visitor_data('does-not-exist'), {'visitors': 0})


class PartitioningTests(TestCase):
    """
    Partitioning is Postgres-only, so on SQLite these assert the guards.

    The conversion itself cannot be exercised here. It is opt-in, run by hand
    against a quiesced site, and documented in analytics/partitioning.py.
    """

    def test_month_bounds_are_half_open(self):
        from datetime import date

        from .partitioning import month_bounds

        start, end = month_bounds(date(2026, 1, 17))
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 2, 1))

    def test_december_rolls_into_the_next_year(self):
        from datetime import date

        from .partitioning import month_bounds

        _, end = month_bounds(date(2026, 12, 3))
        self.assertEqual(end, date(2027, 1, 1))

    def test_partition_name_is_sortable(self):
        from datetime import date

        from .partitioning import partition_name

        self.assertTrue(partition_name(date(2026, 3, 1)).endswith('y2026m03'))

    def test_unsupported_backend_reports_not_partitioned(self):
        from django.db import connection

        from .partitioning import is_partitioned, is_supported

        if connection.vendor != 'postgresql':
            self.assertFalse(is_supported())
            self.assertFalse(is_partitioned())

    def test_ensure_partitions_is_a_no_op_when_unsupported(self):
        from django.db import connection

        from .partitioning import ensure_partitions

        if connection.vendor != 'postgresql':
            self.assertEqual(ensure_partitions(), [])

    def test_convert_refuses_on_an_unsupported_backend(self):
        from django.db import connection

        from .partitioning import convert

        if connection.vendor != 'postgresql':
            with self.assertRaises(RuntimeError):
                convert()


class IndexableFilterTests(TestCase):
    """
    Guards the fix for a real regression found by the benchmark.

    Filtering a raw table with ``occurred_at__date__gte`` wraps the column in a
    function, which makes both the BRIN and the B-tree index unusable. It
    measured 232 ms on a million rows where a plain range bound measured 6 ms,
    and it is invisible in a small test database — so it is asserted against
    the generated SQL rather than against timing.
    """

    def setUp(self) -> None:
        self.start, self.end = reports.date_range(30)

    def _sql_for(self, queryset) -> str:
        return str(queryset.query).lower()

    def test_bounds_are_half_open_and_cover_the_last_day(self):
        from datetime import timedelta

        start_at, end_at = reports.as_datetime_bounds(self.start, self.end)
        self.assertEqual(start_at.date(), self.start)
        self.assertEqual(end_at.date(), self.end + timedelta(days=1))
        self.assertEqual((start_at.hour, start_at.minute), (0, 0))

    def test_referrer_query_does_not_cast_the_timestamp(self):
        start_at, end_at = reports.as_datetime_bounds(self.start, self.end)
        sql = self._sql_for(
            Session.objects.filter(started_at__gte=start_at, started_at__lt=end_at)
        )
        self.assertNotIn('cast_date', sql)

    def test_report_helpers_avoid_date_casts(self):
        """Every raw-table report must filter on the bare timestamp column."""
        import inspect

        source = inspect.getsource(reports)
        # The only permitted occurrence is the docstring explaining the ban.
        self.assertEqual(source.count('__date__gte'), 1)
        self.assertEqual(source.count('__date__lte'), 0)


@override_settings(TRUSTED_PROXY_COUNT=0)
class VisitorIPListingTests(BufferIsolatedTestCase):
    """
    The raw-address listing — the one place an IP is stored in the clear.

    These also pin the isolation guarantee: turning the feature on must not put
    an address into any other table.
    """

    def _buffer(self, ip=PUBLIC_IP, path='/', ua=CHROME_UA, country='CI'):
        record(
            KIND_PAGEVIEW,
            visitor_id=privacy.hash_visitor(ip, ua),
            ip_hash=privacy.hash_ip(ip),
            ip_address=ip,
            user_agent=ua,
            client_hints={},
            path=path,
            query_hash='',
            params={},
            referrer_host='',
            referrer_url='',
            country_hint=country,
            language='en-US',
            status_code=200,
            response_ms=10,
            user_id=None,
            occurred_at=timezone.now().timestamp(),
            is_spa_navigation=False,
        )

    def test_address_is_recorded_in_the_clear(self):
        self._buffer()
        flush()
        self.assertEqual(VisitorIP.objects.get().ip_address, PUBLIC_IP)

    def test_public_address_is_flagged_public(self):
        self._buffer()
        flush()
        self.assertTrue(VisitorIP.objects.get().is_public)

    def test_private_address_is_flagged_not_public(self):
        self._buffer(ip='127.0.0.1')
        flush()
        self.assertFalse(VisitorIP.objects.get().is_public)

    def test_repeat_visits_increment_rather_than_duplicate(self):
        self._buffer(path='/')
        self._buffer(path='/#skills')
        flush()
        self.assertEqual(VisitorIP.objects.count(), 1)
        row = VisitorIP.objects.get()
        self.assertEqual(row.visit_count, 2)
        self.assertEqual(row.last_path, '/#skills')

    def test_counts_accumulate_across_separate_flushes(self):
        self._buffer()
        flush()
        self._buffer()
        flush()
        self.assertEqual(VisitorIP.objects.get().visit_count, 2)

    def test_distinct_addresses_get_distinct_rows(self):
        self._buffer(ip=PUBLIC_IP)
        self._buffer(ip=FORGED_IP)
        flush()
        self.assertEqual(VisitorIP.objects.count(), 2)

    def test_country_and_bot_flag_are_captured(self):
        self._buffer(ua='Googlebot/2.1')
        flush()
        row = VisitorIP.objects.get()
        self.assertEqual(row.country, 'CI')
        self.assertTrue(row.is_bot)

    @override_settings(ANALYTICS={'STORE_RAW_IPS': False})
    def test_feature_switch_stops_collection(self):
        self._buffer()
        flush()
        self.assertEqual(VisitorIP.objects.count(), 0)
        # The rest of the pipeline keeps working with the listing switched off.
        self.assertEqual(PageView.objects.count(), 1)

    @override_settings(ANALYTICS={'STORE_PRIVATE_IPS': False})
    def test_private_addresses_can_be_excluded(self):
        self._buffer(ip='127.0.0.1')
        self._buffer(ip=PUBLIC_IP)
        flush()
        self.assertEqual(
            list(VisitorIP.objects.values_list('ip_address', flat=True)), [PUBLIC_IP]
        )

    def test_raw_address_does_not_leak_into_the_session_table(self):
        """The isolation guarantee: only VisitorIP holds the address."""
        self._buffer()
        flush()
        session = Session.objects.get()
        self.assertEqual(session.ip_truncated, '93.184.216.0')
        self.assertNotEqual(session.ip_truncated, PUBLIC_IP)
        self.assertNotIn(PUBLIC_IP, session.ip_hash)

    def test_visitor_hash_is_unchanged_by_the_feature(self):
        self._buffer()
        flush()
        self.assertNotIn(PUBLIC_IP, Visitor.objects.get().visitor_id)


class VisitorIPRetentionTests(TestCase):
    def setUp(self) -> None:
        now = timezone.now()
        VisitorIP.objects.create(
            ip_address=PUBLIC_IP, is_public=True, visit_count=1,
            first_seen_at=now - timedelta(days=300), last_seen_at=now - timedelta(days=200),
        )
        VisitorIP.objects.create(
            ip_address=FORGED_IP, is_public=True, visit_count=1,
            first_seen_at=now - timedelta(days=5), last_seen_at=now - timedelta(days=1),
        )

    def test_expired_addresses_are_deleted(self):
        enforce_retention()
        self.assertEqual(
            list(VisitorIP.objects.values_list('ip_address', flat=True)), [FORGED_IP]
        )

    @override_settings(ANALYTICS={'IP_RETENTION_DAYS': 7})
    def test_retention_window_is_configurable(self):
        enforce_retention()
        self.assertEqual(VisitorIP.objects.count(), 1)

    def test_retention_is_idempotent(self):
        enforce_retention()
        remaining = VisitorIP.objects.count()
        enforce_retention()
        self.assertEqual(VisitorIP.objects.count(), remaining)


class VisitorIPSubjectRequestTests(TestCase):
    def setUp(self) -> None:
        now = timezone.now()
        VisitorIP.objects.create(
            ip_address=PUBLIC_IP, is_public=True, visit_count=7,
            first_seen_at=now, last_seen_at=now, last_path='/#resume',
        )

    def test_export_returns_the_row(self):
        payload = export_ip_data(PUBLIC_IP)
        self.assertTrue(payload['held'])
        self.assertEqual(payload['visit_count'], 7)

    def test_export_of_an_unknown_address_is_not_an_error(self):
        self.assertFalse(export_ip_data('1.2.3.4')['held'])

    def test_delete_removes_the_row(self):
        self.assertEqual(delete_ip_data(PUBLIC_IP), 1)
        self.assertEqual(VisitorIP.objects.count(), 0)

    def test_delete_of_an_unknown_address_is_a_no_op(self):
        self.assertEqual(delete_ip_data('1.2.3.4'), 0)


class VisitorIPAdminTests(TestCase):
    def setUp(self) -> None:
        self.superuser = get_user_model().objects.create_superuser(
            'owner', 'owner@example.com', 'not-a-real-password-1'
        )
        self.client.force_login(self.superuser)
        now = timezone.now()
        VisitorIP.objects.create(
            ip_address=PUBLIC_IP, is_public=True, visit_count=3,
            first_seen_at=now, last_seen_at=now,
        )
        VisitorIP.objects.create(
            ip_address='10.0.0.9', is_public=False, visit_count=1,
            first_seen_at=now, last_seen_at=now,
        )

    def test_model_is_registered(self):
        self.assertIn(VisitorIP, admin.site._registry)

    def test_listing_shows_public_addresses(self):
        response = self.client.get(VISITOR_IP_CHANGELIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, PUBLIC_IP)

    def test_private_addresses_are_hidden_by_default(self):
        response = self.client.get(VISITOR_IP_CHANGELIST_URL)
        self.assertNotContains(response, '10.0.0.9')

    def test_private_addresses_are_reachable_through_the_filter(self):
        response = self.client.get(f'{VISITOR_IP_CHANGELIST_URL}?is_public__exact=0')
        self.assertContains(response, '10.0.0.9')

    def test_rows_cannot_be_added_or_edited(self):
        model_admin = VisitorIPAdmin(VisitorIP, admin.site)
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))

    def test_superuser_may_delete_for_erasure_requests(self):
        model_admin = VisitorIPAdmin(VisitorIP, admin.site)

        class FakeRequest:
            user = self.superuser

        self.assertTrue(model_admin.has_delete_permission(FakeRequest()))


class VisitorIPQueryBudgetTests(BufferIsolatedTestCase):
    """
    The address listing must not cost a query per record.

    A get_or_create per buffered row would turn a 500-row flush into 1000
    queries, which is exactly the kind of thing that only shows up in
    production. The batch collapses to distinct addresses first.
    """

    def _buffer(self, ip, path='/'):
        record(
            KIND_PAGEVIEW,
            visitor_id=privacy.hash_visitor(ip, CHROME_UA),
            ip_hash=privacy.hash_ip(ip),
            ip_address=ip,
            user_agent=CHROME_UA,
            client_hints={},
            path=path,
            query_hash='',
            params={},
            referrer_host='',
            referrer_url='',
            country_hint='CI',
            language='en-US',
            status_code=200,
            response_ms=10,
            user_id=None,
            occurred_at=timezone.now().timestamp(),
            is_spa_navigation=False,
        )

    def test_one_address_repeated_stays_cheap(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for index in range(40):
            self._buffer(PUBLIC_IP, path=f'/#p{index}')

        with CaptureQueriesContext(connection) as captured:
            flush()

        self.assertEqual(VisitorIP.objects.get().visit_count, 40)
        self.assertLess(
            len(captured), 20,
            f'flush used {len(captured)} queries for 40 records from one address',
        )

    def test_many_addresses_stay_bounded(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for index in range(40):
            self._buffer(f'93.184.216.{index + 1}')

        with CaptureQueriesContext(connection) as captured:
            flush()

        self.assertEqual(VisitorIP.objects.count(), 40)
        self.assertLess(
            len(captured), 30,
            f'flush used {len(captured)} queries for 40 distinct addresses',
        )

    def test_query_count_does_not_grow_with_the_batch(self):
        """
        The flush must cost the same number of queries at any batch size.

        This is the property that matters, and it is stronger than any fixed
        threshold: it catches a per-row query being reintroduced anywhere in
        the flush path, not just in the code this test was written for. It was
        added after the attribution write was found doing one UPDATE per new
        visitor — 50 queries for 40 visitors, versus 13 now.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        counts = {}
        for size in (5, 50):
            buffer.clear()
            Visitor.objects.all().delete()
            VisitorIP.objects.all().delete()
            for index in range(size):
                self._buffer(f'93.184.{index // 254}.{index % 254 + 1}', path=f'/#p{index}')

            with CaptureQueriesContext(connection) as captured:
                flush()
            counts[size] = len(captured)

        self.assertEqual(
            counts[5], counts[50],
            f'flush cost grew with batch size: {counts}. Something in the '
            f'flush path is running one query per record.',
        )
