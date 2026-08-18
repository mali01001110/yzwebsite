from django.contrib import admin
from django.utils.text import Truncator

from .models import ContactMessage, Visitor

MESSAGE_PREVIEW_LENGTH = 90
USER_AGENT_PREVIEW_LENGTH = 60


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    """
    Read-only list of the IP addresses that have loaded the site.

    Rows are written by VisitorTrackingMiddleware, so nothing here is editable:
    a hand-edited address would misrepresent the traffic record. Deletion stays
    available because an IP address is personal data and may have to be erased
    on request.
    """

    list_display = (
        'ip_address',
        'is_public',
        'visit_count',
        'last_seen',
        'first_seen',
        'last_path',
        'user_agent_preview',
    )
    list_filter = ('is_public', 'last_seen')
    search_fields = ('ip_address', 'last_path', 'last_user_agent')
    date_hierarchy = 'last_seen'
    ordering = ('-last_seen',)

    @admin.display(description='User agent')
    def user_agent_preview(self, visitor):
        return Truncator(visitor.last_user_agent).chars(USER_AGENT_PREVIEW_LENGTH)

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        """Visitors are observed, never entered by hand."""
        return False

    def has_change_permission(self, request, obj=None):
        return False


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
