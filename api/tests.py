from django.contrib import admin
from django.test import RequestFactory, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from .admin import ContactMessageAdmin, VisitorAdmin
from .client_ip import get_client_ip, is_public_ip
from .models import ContactMessage, Visitor

CONTACT_URL = '/api/contact/'
# Deliberately not the 203.0.113.0/24 documentation range: those addresses are
# reserved, so `is_public_ip` correctly reports them as not globally routable.
PUBLIC_IP = '93.184.216.34'
FORGED_IP = '8.8.8.8'
PROXY_IP = '10.0.0.1'

VALID_PAYLOAD = {
    'name': 'Ada Lovelace',
    'email': 'ada@example.com',
    'message': 'Hello, I would like to discuss a project.',
}


class ContactMessageSubmissionTests(TestCase):
    """Covers the public endpoint that feeds the admin inbox."""

    def setUp(self):
        self.client = APIClient()

    def test_valid_submission_is_stored(self):
        response = self.client.post(CONTACT_URL, VALID_PAYLOAD, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContactMessage.objects.count(), 1)

        stored = ContactMessage.objects.get()
        self.assertEqual(stored.name, VALID_PAYLOAD['name'])
        self.assertEqual(stored.email, VALID_PAYLOAD['email'])
        self.assertEqual(stored.message, VALID_PAYLOAD['message'])
        self.assertFalse(stored.is_read)
        self.assertIsNotNone(stored.submitted_at)

    def test_response_never_echoes_stored_record(self):
        """The public reply stays a bare acknowledgement, not a data leak."""
        response = self.client.post(CONTACT_URL, VALID_PAYLOAD, format='json')

        self.assertEqual(list(response.json().keys()), ['detail'])

    def test_surrounding_whitespace_is_trimmed(self):
        self.client.post(
            CONTACT_URL,
            {'name': '  Ada  ', 'email': ' ada@example.com ', 'message': '  hi there  '},
            format='json',
        )

        stored = ContactMessage.objects.get()
        self.assertEqual(stored.name, 'Ada')
        self.assertEqual(stored.message, 'hi there')

    def test_whitespace_only_fields_are_rejected(self):
        response = self.client.post(
            CONTACT_URL,
            {'name': '   ', 'email': 'ada@example.com', 'message': '   '},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.json())
        self.assertIn('message', response.json())
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_missing_fields_are_rejected(self):
        response = self.client.post(CONTACT_URL, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.json().keys()), {'name', 'email', 'message'})
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_malformed_email_is_rejected(self):
        response = self.client.post(
            CONTACT_URL, {**VALID_PAYLOAD, 'email': 'not-an-email'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_oversized_fields_are_rejected(self):
        oversized = {
            'name': 'x' * (ContactMessage.NAME_MAX_LENGTH + 1),
            'email': 'ada@example.com',
            'message': 'y' * (ContactMessage.MESSAGE_MAX_LENGTH + 1),
        }

        response = self.client.post(CONTACT_URL, oversized, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.json())
        self.assertIn('message', response.json())
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_error_body_is_a_flat_field_to_messages_map(self):
        """The frontend error parser depends on this shape."""
        response = self.client.post(
            CONTACT_URL, {**VALID_PAYLOAD, 'email': 'nope'}, format='json'
        )

        errors = response.json()
        self.assertIsInstance(errors['email'], list)
        self.assertIsInstance(errors['email'][0], str)

    def test_read_flag_cannot_be_set_by_the_public(self):
        """A visitor must not be able to pre-mark their own message as read."""
        self.client.post(CONTACT_URL, {**VALID_PAYLOAD, 'is_read': True}, format='json')

        self.assertFalse(ContactMessage.objects.get().is_read)

    def test_get_is_not_allowed(self):
        response = self.client.get(CONTACT_URL)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ContactMessageOrderingTests(TestCase):
    def test_newest_message_is_listed_first(self):
        older = ContactMessage.objects.create(**VALID_PAYLOAD)
        newer = ContactMessage.objects.create(**{**VALID_PAYLOAD, 'name': 'Grace'})

        self.assertEqual(list(ContactMessage.objects.all()), [newer, older])


class ContactMessageAdminTests(TestCase):
    """The admin inbox is the feature the site owner actually interacts with."""

    def setUp(self):
        self.model_admin = ContactMessageAdmin(ContactMessage, admin.site)

    def test_model_is_registered(self):
        self.assertIn(ContactMessage, admin.site._registry)

    def test_messages_cannot_be_added_from_the_admin(self):
        self.assertFalse(self.model_admin.has_add_permission(None))

    def test_visitor_content_is_read_only(self):
        for field in ('name', 'email', 'message', 'submitted_at'):
            self.assertIn(field, self.model_admin.readonly_fields)

    def test_triage_flag_stays_editable(self):
        self.assertNotIn('is_read', self.model_admin.readonly_fields)

    def test_long_message_preview_is_truncated(self):
        record = ContactMessage.objects.create(**{**VALID_PAYLOAD, 'message': 'z' * 500})

        preview = self.model_admin.message_preview(record)

        self.assertLess(len(preview), 500)
        self.assertTrue(preview.endswith('…'))

    def test_mark_as_read_action_updates_selection(self):
        ContactMessage.objects.create(**VALID_PAYLOAD)
        request = type('Request', (), {})()
        self.model_admin.message_user = lambda *args, **kwargs: None

        self.model_admin.mark_as_read(request, ContactMessage.objects.all())

        self.assertTrue(ContactMessage.objects.get().is_read)


class ClientIpResolutionTests(TestCase):
    """The recorded address is only as trustworthy as this resolution step."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, **headers):
        return self.factory.get('/', **headers)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_socket_peer_is_used_without_a_proxy(self):
        request = self._request(REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_forwarded_header_is_ignored_without_a_proxy(self):
        """With nothing in front of Django the header is pure visitor input."""
        request = self._request(REMOTE_ADDR=PUBLIC_IP, HTTP_X_FORWARDED_FOR=FORGED_IP)

        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_client_is_read_from_behind_one_proxy(self):
        request = self._request(REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR=PUBLIC_IP)

        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_prepended_forgery_cannot_displace_the_real_address(self):
        """A visitor sending their own header only pushes it left of ours."""
        request = self._request(
            REMOTE_ADDR=PROXY_IP,
            HTTP_X_FORWARDED_FOR=f'{FORGED_IP}, 1.1.1.1, {PUBLIC_IP}',
        )

        self.assertEqual(get_client_ip(request), PUBLIC_IP)

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_hop_count_selects_the_right_entry(self):
        request = self._request(
            REMOTE_ADDR=PROXY_IP,
            HTTP_X_FORWARDED_FOR=f'{FORGED_IP}, {PUBLIC_IP}, {PROXY_IP}',
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
        request = self._request(REMOTE_ADDR='')

        self.assertIsNone(get_client_ip(request))

    def test_public_and_private_ranges_are_distinguished(self):
        self.assertTrue(is_public_ip(PUBLIC_IP))
        for private in ('127.0.0.1', '10.0.0.4', '192.168.1.20', '::1'):
            self.assertFalse(is_public_ip(private), private)

    def test_reserved_ranges_do_not_count_as_public(self):
        """Documentation and benchmark blocks are not routable on the internet."""
        for reserved in ('203.0.113.10', '198.51.100.7', '192.0.2.1'):
            self.assertFalse(is_public_ip(reserved), reserved)


class VisitorRecordingTests(TestCase):
    def test_first_visit_creates_the_row(self):
        Visitor.objects.record_visit(PUBLIC_IP, '/projects', 'Firefox')

        visitor = Visitor.objects.get()
        self.assertEqual(visitor.ip_address, PUBLIC_IP)
        self.assertEqual(visitor.visit_count, 1)
        self.assertTrue(visitor.is_public)
        self.assertEqual(visitor.last_path, '/projects')

    def test_repeat_visit_increments_instead_of_duplicating(self):
        Visitor.objects.record_visit(PUBLIC_IP, '/', 'Firefox')
        Visitor.objects.record_visit(PUBLIC_IP, '/contact', 'Firefox')

        self.assertEqual(Visitor.objects.count(), 1)
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.visit_count, 2)
        self.assertEqual(visitor.last_path, '/contact')

    def test_last_seen_advances_on_a_repeat_visit(self):
        Visitor.objects.record_visit(PUBLIC_IP, '/', 'Firefox')
        first_seen = Visitor.objects.get().last_seen

        Visitor.objects.record_visit(PUBLIC_IP, '/', 'Firefox')

        self.assertGreater(Visitor.objects.get().last_seen, first_seen)

    def test_missing_address_records_nothing(self):
        written = Visitor.objects.record_visit(None, '/', 'Firefox')

        self.assertEqual(written, 0)
        self.assertEqual(Visitor.objects.count(), 0)

    def test_overlong_values_are_truncated_to_fit(self):
        Visitor.objects.record_visit(PUBLIC_IP, '/' + 'a' * 500, 'u' * 900)

        visitor = Visitor.objects.get()
        self.assertEqual(len(visitor.last_path), Visitor.PATH_MAX_LENGTH)
        self.assertEqual(len(visitor.last_user_agent), Visitor.USER_AGENT_MAX_LENGTH)

    def test_private_address_is_flagged_as_not_public(self):
        Visitor.objects.record_visit('127.0.0.1', '/', 'Firefox')

        self.assertFalse(Visitor.objects.get().is_public)


@override_settings(TRUSTED_PROXY_COUNT=0)
class VisitorTrackingMiddlewareTests(TestCase):
    """Exercised through the real stack, so middleware order is covered too."""

    def test_page_view_is_recorded(self):
        self.client.get('/', REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Visitor.objects.get().ip_address, PUBLIC_IP)

    def test_spa_route_is_recorded(self):
        self.client.get('/projects', REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(Visitor.objects.get().last_path, '/projects')

    def test_json_api_call_is_not_a_page_view(self):
        self.client.get('/api/hello/', REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(Visitor.objects.count(), 0)

    def test_admin_browsing_is_not_recorded(self):
        self.client.get('/admin/login/', REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(Visitor.objects.count(), 0)

    def test_contact_submission_is_not_a_page_view(self):
        self.client.post(CONTACT_URL, VALID_PAYLOAD, REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(Visitor.objects.count(), 0)


class VisitorAdminTests(TestCase):
    def setUp(self):
        self.model_admin = VisitorAdmin(Visitor, admin.site)

    def test_model_is_registered(self):
        self.assertIn(Visitor, admin.site._registry)

    def test_visitors_cannot_be_added_or_edited(self):
        self.assertFalse(self.model_admin.has_add_permission(None))
        self.assertFalse(self.model_admin.has_change_permission(None))

    def test_every_field_is_read_only(self):
        readonly = self.model_admin.get_readonly_fields(None)

        for field in ('ip_address', 'visit_count', 'first_seen', 'last_seen'):
            self.assertIn(field, readonly)

    def test_ip_address_is_the_leading_column(self):
        self.assertEqual(self.model_admin.list_display[0], 'ip_address')

    def test_long_user_agent_preview_is_truncated(self):
        visitor = Visitor.objects.create(
            ip_address=PUBLIC_IP,
            first_seen='2026-01-01T00:00:00Z',
            last_seen='2026-01-01T00:00:00Z',
            last_user_agent='u' * 200,
        )

        self.assertLess(len(self.model_admin.user_agent_preview(visitor)), 200)
