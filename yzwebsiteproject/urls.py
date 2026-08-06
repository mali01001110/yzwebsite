"""
URL configuration for yzwebsiteproject.

Django owns `/admin/` and `/api/`; every other path returns the compiled React
app so client-side routing can take over, including on a hard refresh.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

spa_view = TemplateView.as_view(template_name='index.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    re_path(r'^.*$', spa_view, name='spa'),
]
