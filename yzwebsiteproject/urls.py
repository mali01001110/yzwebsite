"""
URL configuration for yzwebsiteproject project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def home(request):
    """
    Welcome page shown at the root URL ( / ).
    Returns a simple JSON listing the available endpoints.
    """
    return JsonResponse({
        "message": "Welcome to yzwebsiteproject API 🎉",
        "endpoints": {
            "admin": "/admin/",
            "hello": "/api/hello/"
        }
    })


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]