
# Reel News - Health Check
#
# Description: Provides a simple endpoint to verify
# that the Django application is running.

from django.http import JsonResponse


def health_check(request):
    return JsonResponse({
        "status": "ok"
    })
