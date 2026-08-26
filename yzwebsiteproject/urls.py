"""
URL configuration for yzwebsiteproject.

Django owns the admin and `/api/`; every other path returns the compiled React
app so client-side routing can take over, including on a hard refresh.
"""
import re

from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

spa_view = TemplateView.as_view(template_name='index.html')

# Backend-owned prefixes are excluded from the catch-all so a slashless or
# unknown path under them still resolves to nothing. That 404 is what lets
# CommonMiddleware's APPEND_SLASH redirect the slashless admin path to its
# canonical form; without the exclusion the catch-all matches first and returns
# the SPA instead. The list lives in settings because the analytics collector
# needs the same prefixes.
SPA_PATTERN = r'^(?!(?:{})(?:/|$)).*$'.format(
    '|'.join(re.escape(prefix) for prefix in settings.BACKEND_URL_PREFIXES)
)

urlpatterns = [
    path(f'{settings.ADMIN_URL_SEGMENT}/', admin.site.urls),
    path('api/', include('api.urls')),
    re_path(SPA_PATTERN, spa_view, name='spa'),
]
