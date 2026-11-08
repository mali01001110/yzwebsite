import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create or synchronize the configured site administrator.'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_ADMIN_USERNAME', '').strip()
        password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')
        if not username or not password:
            raise CommandError(
                'DJANGO_ADMIN_USERNAME and DJANGO_ADMIN_PASSWORD must both be set.'
            )

        user_model = get_user_model()
        lookup = {user_model.USERNAME_FIELD: username}
        user = user_model._default_manager.filter(**lookup).first()

        if user is None:
            user_model._default_manager.create_superuser(
                **lookup,
                password=password,
            )
            self.stdout.write(self.style.SUCCESS('Site administrator created.'))
            return

        if not user.is_superuser:
            raise CommandError(
                f'User "{username}" already exists but is not a superuser.'
            )

        user.set_password(password)
        user.is_active = True
        user.is_staff = True
        user.save(update_fields=['password', 'is_active', 'is_staff'])
        self.stdout.write(self.style.SUCCESS('Site administrator synchronized.'))
