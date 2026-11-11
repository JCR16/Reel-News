from django.urls import path
from .views import feed

urlpatterns = [
    path("", feed, name="feed"),
]
"""
urlpatterns = [
    path("", views.feed, name="feed"),
    path("story/<int:story_id>/", views.story_detail, name="story_detail"),
    path("story/<int:story_id>/sources/", views.story_sources, name="story_sources"),
    path("feed/load-more/", views.load_more, name="load_more"),
]
"""