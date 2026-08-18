from django.db import models
from django.db.models import F
from django.utils import timezone

from .client_ip import is_public_ip


class VisitorManager(models.Manager):
    """Write path for visitor tracking, kept out of the request/response layer."""

    def record_visit(self, ip_address, path, user_agent):
        """
        Register one page view, creating the visitor row on first sight.

        Returns the number of rows written, so callers can tell a recorded
        visit from an ignored one.
        """
        if not ip_address:
            return 0

        visit_time = timezone.now()
        truncated_path = path[:Visitor.PATH_MAX_LENGTH]
        truncated_user_agent = user_agent[:Visitor.USER_AGENT_MAX_LENGTH]

        _, created = self.get_or_create(
            ip_address=ip_address,
            defaults={
                'is_public': is_public_ip(ip_address),
                'visit_count': 1,
                'first_seen': visit_time,
                'last_seen': visit_time,
                'last_path': truncated_path,
                'last_user_agent': truncated_user_agent,
            },
        )
        if created:
            return 1

        # F() so concurrent requests from one address cannot lose increments to
        # a read-modify-write race.
        return self.filter(ip_address=ip_address).update(
            visit_count=F('visit_count') + 1,
            last_seen=visit_time,
            last_path=truncated_path,
            last_user_agent=truncated_user_agent,
        )


class Visitor(models.Model):
    """
    One row per distinct IP address that has loaded a page on the site.

    Aggregated rather than append-only: the site owner wants a list of who has
    visited, and one row per request would grow without bound while burying
    that answer. `visit_count` and `last_seen` preserve the frequency and
    recency that the individual rows would have carried.
    """

    PATH_MAX_LENGTH = 200
    USER_AGENT_MAX_LENGTH = 300

    ip_address = models.GenericIPAddressField(unique=True)
    is_public = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether the address is routable on the public internet.',
    )
    visit_count = models.PositiveIntegerField(default=0)
    first_seen = models.DateTimeField(db_index=True)
    last_seen = models.DateTimeField(db_index=True)
    last_path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    last_user_agent = models.CharField(max_length=USER_AGENT_MAX_LENGTH, blank=True)

    objects = VisitorManager()

    class Meta:
        ordering = ['-last_seen']
        verbose_name = 'Visitor'
        verbose_name_plural = 'Visitors'

    def __str__(self):
        return self.ip_address


class ContactMessage(models.Model):
    """A message submitted by a visitor through the site's contact form."""

    NAME_MAX_LENGTH = 80
    EMAIL_MAX_LENGTH = 120
    MESSAGE_MAX_LENGTH = 2000

    name = models.CharField(max_length=NAME_MAX_LENGTH)
    email = models.EmailField(max_length=EMAIL_MAX_LENGTH)
    message = models.TextField(max_length=MESSAGE_MAX_LENGTH)
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Contact message'
        verbose_name_plural = 'Contact messages'

    def __str__(self):
        return f'{self.name} <{self.email}>'
