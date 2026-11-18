
from django.utils import timezone
from django.db import transaction

from stories.models import RevisionArticle, Story, StoryRevision, Publisher

from stories.services.gemini import generate_story
from stories.services.article_manager import get_or_create_article


@transaction.atomic
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


@transaction.atomic
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


def link_revision_article(
    story: Story,
    revision: StoryRevision,
    article_data: dict,
) -> RevisionArticle:
    """
    Create or reuse an Article and link it to a StoryRevision.
    """

    # Retrieve the article's publisher.
    publisher = Publisher.objects.get(
        publisherid=article_data["publisher_id"]
    )

    # Create the Article if its content hash is new,
    # otherwise reuse the existing record.
    article = get_or_create_article(
        title=article_data["title"],
        link=article_data["link"],
        text=article_data["text"],
        publisher=publisher,
    )

    # Create or retrieve the relationship between
    # the Article and this specific StoryRevision.
    link, created = RevisionArticle.objects.get_or_create(
        articleid=article,
        storyid=story,
        revisionnum=revision.revisionnum,
    )

    return link


def generate_and_save_story(articles: list[dict]) -> Story:
    """
    Generate a story using Gemini and save it to PostgreSQL.
    """

    # Extract the article text for Gemini.
    article_texts = [article["text"] for article in articles]

    # Generate the headline and summary before opening a transaction.
    generated = generate_story(article_texts)

    # Ensure all database operations succeed or fail together.
    with transaction.atomic():

        # Create the Story record.
        story = create_story()

        # Save Gemini's output as the first StoryRevision.
        revision = create_story_revision(
            story,
            headline=generated["headline"],
            summary=generated["summary"],
        )

        # Create or reuse each Article and link it to this revision.
        for article_data in articles:
            link_revision_article(story, revision, article_data)

    # Return the newly created Story.
    return story


def generate_and_save_revision(
    story_id: int,
    articles: list[dict],
) -> StoryRevision:
    """
    Generate a new revision of an existing Story using
    an updated list of source articles.
    """

    # Extract the article texts for Gemini.
    article_texts = [article["text"] for article in articles]

    # Generate the updated headline and summary.
    generated = generate_story(article_texts)

    # Create the new revision inside a database transaction.
    with transaction.atomic():

        # Lock the Story record to prevent simultaneous revision updates.
        story = Story.objects.select_for_update().get(storyid=story_id)

        # Create the next revision using Gemini's generated content.
        revision = create_story_revision(
            story,
            headline=generated["headline"],
            summary=generated["summary"],
        )

        # Create or reuse each Article and link it to this revision.
        for article_data in articles:
            link_revision_article(story, revision, article_data)

    # Return the newly created revision.
    return revision