# Reel News - API Health Check
#
# Developed by: Reel News team
# Description: Provides a health-check endpoint that confirms
# the Django REST API is running and responding to requests.
#
# External libraries:
# - Django REST Framework: api_view decorator and Response class.
#
# External code:
# - No third-party source code copied or adapted.

from rest_framework.decorators import api_view
from rest_framework.response import Response


# Connected to a request inside urls.py
@api_view(["GET"])          # tells Django RF that this endpoint accepts HTTP GET requests
def health_check(request):  # the function Django executes when someone visits the endpoint
    return Response({       # converts Python dictionary into HTTP response containing JSON
        "status": "ok",
        "message": "Reel News Django API is running!"
    })