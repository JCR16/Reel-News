from django.contrib.auth import login
from django.shortcuts import redirect, render
from .forms import SignUpForm

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from stories.models import Story
from .services.bookmark_manager import (
    bookmark_story,
    unbookmark_story,
    is_bookmarked,
    get_bookmarks,
)

def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("feed")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})

@login_required
@require_POST
def add_bookmark(request, story_id):
    """
    Bookmark a story for the currently authenticated user.
    """

    try:
        bookmark, created = bookmark_story(
            request.user,
            story_id,
        )

    except Story.DoesNotExist:
        return JsonResponse(
            {"error": "Story not found."},
            status=404,
        )

    except ValueError as error:
        return JsonResponse(
            {"error": str(error)},
            status=400,
        )

    return JsonResponse({
        "story_id": story_id,
        "bookmarked": True,
        "created": created,
    }, status=201 if created else 200)

@login_required
@require_POST
def remove_bookmark(request, story_id):
    """
    Remove a story from the currently authenticated
    user's bookmarks.
    """

    # Remove the bookmark if it exists.
    removed = unbookmark_story(
        request.user,
        story_id,
    )

    # Return the resulting bookmark state.
    return JsonResponse({
        "story_id": story_id,
        "bookmarked": False,
        "removed": removed,
    }, status=200)

@login_required
@require_GET
def bookmark_status(request, story_id):
    """
    Check whether the currently authenticated user
    has bookmarked a particular story.
    """

    # Retrieve the user's bookmark status for this story.
    bookmarked = is_bookmarked(
        request.user,
        story_id,
    )

    # Return the current bookmark state.
    return JsonResponse({
        "story_id": story_id,
        "bookmarked": bookmarked,
    }, status=200)

@login_required
@require_GET
def list_bookmarks(request):
    """
    Retrieve the currently authenticated user's bookmarks,
    ordered from newest to oldest.
    """

    # Retrieve all publicly accessible bookmarked stories.
    bookmarks = get_bookmarks(request.user)

    # Convert the bookmark objects into JSON-compatible data.
    data = [
        {
            "story_id": bookmark.storyid_id,
            "story_status": bookmark.storyid.status,
            "published_revision_num": bookmark.storyid.publishedrevisionnum,
            "date_bookmarked": bookmark.datecreated.isoformat(),
        }
        for bookmark in bookmarks
    ]

    return JsonResponse({
        "count": len(data),
        "bookmarks": data,
    }, status=200)