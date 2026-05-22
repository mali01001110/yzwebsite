from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def hello_world(request):
    """
    A simple API endpoint that returns a greeting message.
    Accessible at: /api/hello/
    """
    return Response({"message": "Hello from Django!"})