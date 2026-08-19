"""
Routes for the analytics app.

Mounted under the project's existing ``/api/`` namespace from ``api/urls.py``,
and using the same conventions found there: a flat ``urlpatterns``, a
trailing-slash path, and a ``name`` matching the view function.
"""
from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('events/', views.ingest_events, name='ingest_events'),
]
