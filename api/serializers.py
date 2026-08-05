from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    """
    Validates visitor-submitted contact form payloads.

    Length limits, email formatting and blank rejection are inherited from the
    model field definitions, so the constraints stay defined in exactly one
    place. DRF trims surrounding whitespace before validating, which turns
    whitespace-only submissions into rejected blanks.
    """

    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'message', 'submitted_at']
        read_only_fields = ['id', 'submitted_at']
