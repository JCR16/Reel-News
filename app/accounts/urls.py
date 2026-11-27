from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),

    # Bookmark management endpoints
    path(
        "bookmarks/<int:story_id>/add/",
        views.add_bookmark,
        name="add_bookmark",
    ),
    path(
        "bookmarks/<int:story_id>/remove/",
        views.remove_bookmark,
        name="remove_bookmark",
    ),
    path(
        "bookmarks/<int:story_id>/status/",
        views.bookmark_status,
        name="bookmark_status",
    ),
    path(
        "bookmarks/",
        views.list_bookmarks,
        name="list_bookmarks",
    ),
]