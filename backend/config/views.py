from rest_framework.decorators import api_view
from rest_framework.response import Response

# Connected to a request inside urls.py
@api_view(["GET"])          # tells Django RF that this endpoint accepts HTTP GET requests
def health_check(request):  # the function Django executes when someone visits the endpoint
    return Response({       # converts Python dictionary into HTTP response containing JSON
        "status": "ok",
        "message": "Reel News Django API is running!"
    })