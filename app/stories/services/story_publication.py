from django.db import transaction

from stories.models import Story, RevisionArticle
from stories.services.story_manager import cleanup_unused_article_text


@transaction.atomic
def approve_revision(
    story_id: int,
    expected_revision_num: int,
):
    """
    Approve the current Draft revision of a story.

    Update the published revision while preserving previous
    revisions and their associated source articles.
    """

    # Lock the story to prevent concurrent editorial changes.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Archived stories must be restored before approval.
    if story.status == "Archived":
        raise ValueError(
            "Archived stories must be restored before approving revisions."
        )

    # Ensure the current revision matches the revision
    # the administrator intended to approve.
    if (
        expected_revision_num is None
        or story.currentrevisionnum != expected_revision_num
    ):
        raise ValueError(
            "The current revision has changed. Please review it again."
        )

    # Retrieve the current revision.
    revision = story.revisions.filter(
        revisionnum=story.currentrevisionnum
    ).first()

    # Only Draft revisions can be approved.
    if revision is None or revision.status != "Draft":
        raise ValueError("Only Draft revisions can be approved.")

    # Mark the current revision as Published.
    revision.status = "Published"
    revision.save(update_fields=["status"])

    # Update the story's publicly visible revision.
    story.publishedrevisionnum = revision.revisionnum
    story.status = "Published"

    story.save(
        update_fields=["publishedrevisionnum", "status"]
    )

    # Collect the articles associated with the approved revision.
    article_ids = list(
        RevisionArticle.objects.filter(
            storyid=story,
            revisionnum=revision.revisionnum,
        ).values_list("articleid_id", flat=True)
    )

    # Clean up article text only after publication commits.
    transaction.on_commit(
        lambda ids=article_ids: cleanup_unused_article_text(ids)
    )

    return revision

@transaction.atomic
def reject_revision(
    story_id: int,
    feedback: str,
    expected_revision_num: int,
):
    """
    Reject the current Draft revision of a story and save
    the administrator's review feedback.

    Preserve the previously published revision, if one exists.
    """

    # Lock the story to prevent concurrent editorial changes.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Archived stories cannot have their revisions rejected.
    if story.status == "Archived":
        raise ValueError(
            "Archived stories must be restored before rejecting revisions."
        )

    # Ensure the administrator is rejecting the intended revision.
    if (
        expected_revision_num is None
        or story.currentrevisionnum != expected_revision_num
    ):
        raise ValueError(
            "The current revision has changed. Please review it again."
        )

    # Retrieve the current revision.
    revision = story.revisions.filter(
        revisionnum=story.currentrevisionnum
    ).first()

    # Only Draft revisions can be rejected.
    if revision is None or revision.status != "Draft":
        raise ValueError("Only Draft revisions can be rejected.")

    # Require meaningful review feedback.
    if not feedback or not feedback.strip():
        raise ValueError("Review feedback is required.")

    # Reject the revision and save the feedback.
    revision.status = "Rejected"
    revision.reviewfeedback = feedback.strip()

    revision.save(
        update_fields=["status", "reviewfeedback"]
    )

    # If the story has never been published, mark it as
    # Changes Needed. Otherwise, preserve its published status.
    if story.publishedrevisionnum is None:
        story.status = "Changes Needed"
        story.save(update_fields=["status"])

    return revision

@transaction.atomic
def update_review_feedback(
    story_id: int,
    feedback: str,
    expected_revision_num: int,
):
    """
    Update the review feedback of the current Rejected revision
    without creating a new revision or changing its status.
    """

    # Lock the story to prevent concurrent editorial changes.
    story = Story.objects.select_for_update().get(pk=story_id)

    # Archived stories cannot be modified.
    if story.status == "Archived":
        raise ValueError("Archived stories cannot be modified.")

    # Ensure the administrator is editing the intended revision.
    if (
        expected_revision_num is None
        or story.currentrevisionnum != expected_revision_num
    ):
        raise ValueError(
            "The current revision has changed. Please review it again."
        )

    # Retrieve the current revision.
    revision = story.revisions.filter(
        revisionnum=story.currentrevisionnum
    ).first()

    # Feedback can only be modified on Rejected revisions.
    if revision is None or revision.status != "Rejected":
        raise ValueError(
            "Review feedback can only be updated on Rejected revisions."
        )

    # Update the feedback without modifying the revision status.
    revision.reviewfeedback = feedback
    revision.save(update_fields=["reviewfeedback"])

    return revision