"""
Routing guarantees for the root URLconf.

The admin's location is configurable (``DJANGO_ADMIN_URL``), which makes two
things worth pinning down: the admin has to be reachable wherever it was moved
to, and ``/admin/`` must never serve it again in any environment.
"""
import re

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from .urls import SPA_PATTERN


class AdminUrlConfigurationTests(SimpleTestCase):
    def test_admin_is_mounted_at_the_configured_segment(self):
        self.assertEqual(
            reverse('admin:index'), f'/{settings.ADMIN_URL_SEGMENT}/'
        )

    def test_segment_holds_no_regex_metacharacters(self):
        """The invariant that lets the segment be interpolated into a pattern."""
        self.assertRegex(settings.ADMIN_URL_SEGMENT, r'^[A-Za-z0-9_-]{1,64}$')

    def test_configured_admin_is_excluded_from_analytics(self):
        self.assertIn(
            f'/{settings.ADMIN_URL_SEGMENT}/',
            settings.ANALYTICS['EXCLUDE_PATH_PREFIXES'],
        )

    def test_admin_is_never_served_from_the_default_path(self):
        """The requirement the setting exists for, asserted in every environment."""
        self.assertNotEqual(settings.ADMIN_URL_SEGMENT, 'admin')
        self.assertNotEqual(settings.DEV_ADMIN_URL_SEGMENT, 'admin')

    def test_default_admin_path_now_belongs_to_the_spa(self):
        self.assertNotIn('admin', settings.BACKEND_URL_PREFIXES)
        for path in ('/admin/', '/admin/login/'):
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, 'spa')


class SpaCatchAllTests(SimpleTestCase):
    def test_backend_prefixes_are_excluded(self):
        for prefix in settings.BACKEND_URL_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertIsNone(re.match(SPA_PATTERN, prefix))
                self.assertIsNone(re.match(SPA_PATTERN, f'{prefix}/anything'))

    def test_client_routes_are_matched(self):
        # 'administration' shares a prefix with 'admin' but is not under it, so
        # the exclusion has to end on a segment boundary rather than a substring.
        for path in ('', 'projects', 'about-me', 'administration', 'apiary'):
            with self.subTest(path=path):
                self.assertIsNotNone(re.match(SPA_PATTERN, path))

    def test_spa_owns_the_site_root(self):
        self.assertEqual(resolve('/').url_name, 'spa')
