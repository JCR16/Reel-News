
from django.utils import timezone

from stories.models import Story, StoryRevision


def create_story() -> Story:
    """
    Create a new Story record in the database.

    The headline and summary will be stored separately
    in a StoryRevision record.
    """

    # Get the current date and time for the story's timestamps.
    now = timezone.now()

    # Create the Story record.
    # PostgreSQL automatically generates the storyID.
    # currentRevisionNum starts as NULL because we haven't
    # created the first StoryRevision yet.
    story = Story.objects.create(
        currentrevisionnum=None,
        datecreated=now,
        datemodified=now,
        status="Draft",
    )

    # Return the saved Story so other functions can reference it.
    return story



def create_story_revision(
    story: Story,
    headline: str,
    summary: str,
) -> StoryRevision:
    """
    Create a new revision of an existing Story.

    Automatically increment the revision number and update
    the Story to reference the newly created revision.
    """

    # Determine the next revision number.
    # New stories start at revision 1.
    next_revision = (story.currentrevisionnum or 0) + 1

    # Create the new revision with its headline and summary.
    revision = StoryRevision.objects.create(
        storyid=story,
        revisionnum=next_revision,
        datecreated=timezone.now(),
        headline=headline,
        summary=summary,
    )

    # Update the Story to reference its newest revision.
    story.currentrevisionnum = next_revision
    story.datemodified = timezone.now()

    # Save the updated revision number and modification timestamp.
    story.save(update_fields=["currentrevisionnum", "datemodified"])

    # Return the newly created revision.
    return revision
