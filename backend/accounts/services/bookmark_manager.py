from django.db import transaction

from accounts.models import Bookmark
from stories.models import Story


@transaction.atomic
def bookmark_story(user, story_id):
    """
    Save a publicly accessible story to a user's bookmarks.

    Returns a tuple containing the Bookmark object and a
    boolean indicating whether a new bookmark was created.
    """

    # Only authenticated users can bookmark stories.
    if not user.is_authenticated:
        raise ValueError("Authentication is required.")

    # Lock the story to prevent concurrent editorial operations
    # from changing or deleting it during bookmark creation.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Only published and archived stories can be bookmarked.
    if story.status not in ("Published", "Archived"):
        raise ValueError("This story is not publicly available.")

    # Ensure the story has a published revision.
    if story.publishedrevisionnum is None:
        raise ValueError("This story has no published revision.")

    # Return the existing bookmark if one already exists.
    return Bookmark.objects.get_or_create(
        userid=user,
        storyid=story,
    )

def unbookmark_story(user, story_id):
    """
    Remove a story from a user's bookmarks.

    Returns True if a bookmark was removed, or False
    if the story was not previously bookmarked.
    """

    # Only authenticated users can remove bookmarks.
    if not user.is_authenticated:
        raise ValueError("Authentication is required.")

    # Delete only the bookmark belonging to this user and story.
    deleted_count, _ = Bookmark.objects.filter(
        userid=user,
        storyid_id=story_id,
    ).delete()

    # Indicate whether a bookmark was actually removed.
    return deleted_count > 0

def is_bookmarked(user, story_id):
    """
    Check whether a user has bookmarked a particular story.

    Returns True if the bookmark exists, otherwise False.
    """

    # Only authenticated users have bookmarks.
    if not user.is_authenticated:
        raise ValueError("Authentication is required.")

    # Check whether the user-story relationship exists.
    return Bookmark.objects.filter(
        userid=user,
        storyid_id=story_id,
    ).exists()

def get_bookmarks(user):
    """
    Retrieve a user's bookmarks, ordered from newest to oldest.

    Only returns bookmarks associated with publicly accessible
    stories, including archived stories.
    """

    # Only authenticated users have bookmarks.
    if not user.is_authenticated:
        raise ValueError("Authentication is required.")

    # Retrieve the user's bookmarks and their associated stories.
    return (
        Bookmark.objects.filter(
            userid=user,
            storyid__status__in=("Published", "Archived"),
            storyid__publishedrevisionnum__isnull=False,
        )
        .select_related("storyid")
        .order_by("-datecreated", "storyid_id")
    )