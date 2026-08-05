from django.urls import path
from . import views

urlpatterns = [
    path('hello/', views.hello_world, name='hello_world'),
    path('contact/', views.submit_contact_message, name='submit_contact_message'),
]