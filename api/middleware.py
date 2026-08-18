"""Request-time capture of site visitors."""
import logging

from .client_ip import get_client_ip
from .models import Visitor

logger = logging.getLogger(__name__)

# Browsing the admin is the owner working on the site, not a visit to it.
IGNORED_PATH_PREFIXES = ('/admin/',)


class VisitorTrackingMiddleware:
    """
    Records the IP address behind each page view for the admin's visitor list.

    Runs after the response is produced so it can distinguish an actual page
    from an asset, an API call or a 404 without duplicating URL knowledge.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if self._is_page_view(request, response):
            self._record(request)

        return response

    def _record(self, request):
        """
        Tracking is incidental to serving the page, so a failure here must
        never turn a working page into a 500 for the visitor.
        """
        try:
            Visitor.objects.record_visit(
                ip_address=get_client_ip(request),
                path=request.path,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception:
            logger.exception('Failed to record visitor for %s', request.path)

    @staticmethod
    def _is_page_view(request, response):
        """
        True only for a browser successfully loading a page.

        Filtering on the rendered content type means static assets, JSON API
        responses and redirects are excluded without listing their URLs here.
        """
        if request.method != 'GET' or response.status_code != 200:
            return False

        if request.path.startswith(IGNORED_PATH_PREFIXES):
            return False

        return response.get('Content-Type', '').startswith('text/html')
