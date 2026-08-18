"""
URL configuration for yzwebsiteproject.

Django owns `/admin/` and `/api/`; every other path returns the compiled React
app so client-side routing can take over, including on a hard refresh.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

spa_view = TemplateView.as_view(template_name='index.html')

# Backend-owned prefixes are excluded from the catch-all so a slashless or
# unknown path under them still resolves to nothing. That 404 is what lets
# CommonMiddleware's APPEND_SLASH redirect '/admin' to '/admin/'; without the
# exclusion the catch-all matches first and returns the SPA instead.
BACKEND_PREFIXES = ('admin', 'api', 'static')
SPA_PATTERN = r'^(?!(?:{})(?:/|$)).*$'.format('|'.join(BACKEND_PREFIXES))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    re_path(SPA_PATTERN, spa_view, name='spa'),
]
