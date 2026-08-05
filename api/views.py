from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .serializers import ContactMessageSerializer


class ContactFormThrottle(AnonRateThrottle):
    """Caps submissions per IP so the public form cannot be flooded."""

    scope = 'contact_form'


@api_view(['GET'])
def hello_world(request):
    """
    A simple API endpoint that returns a greeting message.
    Accessible at: /api/hello/
    """
    return Response({"message": "Hello from Django!"})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ContactFormThrottle])
def submit_contact_message(request):
    """
    Stores a contact form submission for review in the Django admin.
    Accessible at: /api/contact/
    """
    serializer = ContactMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response(
        {'detail': 'Message received. Thanks for reaching out.'},
        status=status.HTTP_201_CREATED,
    )
