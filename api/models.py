from django.db import models


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
