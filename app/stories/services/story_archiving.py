from django.db import transaction
from django.utils import timezone

from ..models import Story


@transaction.atomic
def archive_story(story_id):
    """
    Archive a published story without deleting its revisions,
    source articles, or associated metadata.
    """

    # Lock the story to prevent concurrent editorial changes.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Only published stories can be archived.
    if story.status != "Published":
        raise ValueError("Only published stories can be archived.")

    # Ensure the story has a published revision.
    if story.publishedrevisionnum is None:
        raise ValueError("The story has no published revision.")

    # Update the publication status and modification timestamp.
    story.status = "Archived"
    story.datemodified = timezone.now()

    story.save(update_fields=["status", "datemodified"])

    return story


@transaction.atomic
def restore_story(story_id):
    """
    Restore an archived story to its published state.
    """

    # Lock the story to prevent concurrent editorial changes.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Only archived stories can be restored.
    if story.status != "Archived":
        raise ValueError("Only archived stories can be restored.")

    # Ensure the story still has a published revision.
    if story.publishedrevisionnum is None:
        raise ValueError("The story has no published revision.")

    # Restore the publication status and modification timestamp.
    story.status = "Published"
    story.datemodified = timezone.now()

    story.save(update_fields=["status", "datemodified"])

    return story