from django.contrib import admin
from django.utils.text import Truncator

from .models import ContactMessage

MESSAGE_PREVIEW_LENGTH = 90


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """
    Read-only inbox for visitor messages.

    Visitor-supplied content is never editable from the admin so the archive
    stays a faithful record of what was actually sent; only the internal
    `is_read` triage flag can be changed.
    """

    list_display = ('name', 'email', 'message_preview', 'submitted_at', 'is_read')
    list_display_links = ('name',)
    list_editable = ('is_read',)
    list_filter = ('is_read', 'submitted_at')
    search_fields = ('name', 'email', 'message')
    date_hierarchy = 'submitted_at'
    readonly_fields = ('name', 'email', 'message', 'submitted_at')
    actions = ('mark_as_read', 'mark_as_unread')

    @admin.display(description='Message')
    def message_preview(self, contact_message):
        return Truncator(contact_message.message).chars(MESSAGE_PREVIEW_LENGTH)

    @admin.action(description='Mark selected messages as read')
    def mark_as_read(self, request, queryset):
        updated_count = queryset.update(is_read=True)
        self.message_user(request, f'{updated_count} message(s) marked as read.')

    @admin.action(description='Mark selected messages as unread')
    def mark_as_unread(self, request, queryset):
        updated_count = queryset.update(is_read=False)
        self.message_user(request, f'{updated_count} message(s) marked as unread.')

    def has_add_permission(self, request):
        """Messages originate from the public site, never from the admin."""
        return False
