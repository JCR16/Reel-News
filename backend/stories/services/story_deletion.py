from django.db import transaction

from ..models import (
    Story,
    StoryRevision,
    StoryTag,
    RevisionArticle,
    Article,
    ArticleAuthor,
    ArticleTag,
)


def can_delete_story(story):
    """
    Determine whether a story is eligible for permanent deletion.

    Archived stories can be deleted, as can unpublished stories
    that are still drafts or require changes.
    """
    return (
        story.status == "Archived"
        or (
            story.status in ("Draft", "Changes Needed")
            and story.publishedrevisionnum is None
        )
    )

@transaction.atomic
def delete_story(story_id):
    """
    Permanently delete a story, its revisions, and its relationships.

    Articles are only deleted if they are no longer referenced
    by any revision of any remaining story.
    """

    # Lock the story to prevent concurrent revision changes.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Prevent permanent deletion of ineligible stories.
    if not can_delete_story(story):
        raise ValueError(
            "Only unpublished drafts, stories requiring changes, "
            "and archived stories can be permanently deleted."
        )

    # Collect every article referenced by any revision of this story.
    article_ids = list(
        RevisionArticle.objects.filter(
            storyid=story
        ).values_list("articleid_id", flat=True).distinct()
    )

    # Lock the associated articles before modifying relationships.
    locked_article_ids = list(
        Article.objects.filter(
            pk__in=article_ids
        ).order_by("pk").select_for_update().values_list("pk", flat=True)
    )

    # Break the circular dependency between Story and StoryRevision.
    story.currentrevisionnum = None
    story.publishedrevisionnum = None
    story.save(update_fields=[
        "currentrevisionnum",
        "publishedrevisionnum",
    ])

    # Remove the story's tag and article relationships.
    StoryTag.objects.filter(storyid=story).delete()
    RevisionArticle.objects.filter(storyid=story).delete()

    # Delete all revisions, followed by the story itself.
    StoryRevision.objects.filter(storyid=story).delete()
    story.delete()

    # Identify articles that are no longer referenced by any story.
    orphaned_article_ids = list(
        Article.objects.filter(
            pk__in=locked_article_ids,
            revision_links__isnull=True,
        ).values_list("pk", flat=True)
    )

    # Remove author and tag relationships for orphaned articles.
    ArticleAuthor.objects.filter(
        articleid_id__in=orphaned_article_ids
    ).delete()

    ArticleTag.objects.filter(
        articleid_id__in=orphaned_article_ids
    ).delete()

    # Delete orphaned articles and their associated ArticleText.
    Article.objects.filter(
        pk__in=orphaned_article_ids
    ).delete()

    # Return the number of articles removed.
    return len(orphaned_article_ids)