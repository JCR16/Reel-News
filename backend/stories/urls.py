# Reel News - Story API URL Configuration
#
# Developed by: Reel News team
# Description: Maps incoming story API requests to the
# corresponding Django view.
#
# External libraries:
# - Django URL routing: path() function.
#
# External code:
# - No third-party source code copied or adapted.

from django.urls import path
from .views import get_stories

urlpatterns = [
    path("", get_stories, name="get_stories"),
]