from django.urls import include, path
from . import views

urlpatterns = [
    path('hello/', views.hello_world, name='hello_world'),
    path('contact/', views.submit_contact_message, name='submit_contact_message'),
    # Beacon ingest. Namespaced so the analytics app owns its own routes and
    # unmounting the feature is a one-line change here.
    path('analytics/', include('analytics.urls')),
]