from django.urls import path
from .views import get_stories

urlpatterns = [
    path("", get_stories, name="get_stories"),
]