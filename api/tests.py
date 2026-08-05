from django.contrib import admin
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .admin import ContactMessageAdmin
from .models import ContactMessage

CONTACT_URL = '/api/contact/'

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
