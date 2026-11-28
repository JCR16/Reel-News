
from django.shortcuts import render, get_object_or_404
from .models import Story, StoryRevision, RevisionArticle
from accounts.services.bookmark_manager import get_bookmarks


def story_detail(request, story_id):
    # Only published and archived stories with a published
    # revision are publicly accessible.
    story = get_object_or_404(
        Story,
        storyid=story_id,
        status__in=("Published", "Archived"),
        publishedrevisionnum__isnull=False,
    )

    # Display the published revision rather than the current
    # working revision, which may be awaiting editorial review.
    revision = get_object_or_404(
        StoryRevision,
        storyid_id=story.storyid,
        revisionnum=story.publishedrevisionnum,
        status="Published",
    )

    # Retrieve the source articles associated with the
    # published revision, including publisher information.
    sources = RevisionArticle.objects.filter(
        storyid_id=story.storyid,
        revisionnum=revision.revisionnum,
    ).select_related(
        "articleid",
        "articleid__publisherid",
    ).order_by("articleid_id")

    return render(request, "stories/detail.html", {
        "story": story,
        "revision": revision,
        "sources": sources,
    })


def feed(request):
    # Only published stories with a published revision
    # should appear in the public feed.
    stories = Story.objects.filter(
        status="Published",
        publishedrevisionnum__isnull=False,
    ).order_by("storyid")

    results = []

    # Retrieve the authenticated user's bookmarked story IDs.
    # Anonymous users start with an empty set.
    bookmarked_ids = set()

    if request.user.is_authenticated:
        bookmarked_ids = set(
            get_bookmarks(request.user).values_list(
                "storyid_id", flat=True
            )
        )

    for story in stories:

        # Retrieve the published revision, even if a newer
        # working revision exists.
        revision = StoryRevision.objects.filter(
            storyid_id=story.storyid,
            revisionnum=story.publishedrevisionnum,
            status="Published",
        ).first()

        # Skip stories without a valid published revision.
        if revision is None:
            continue

        results.append({
            "id": story.storyid,
            "headline": revision.headline,
            "summary": revision.summary,
            "image": story.imageurl,

            # Whether the user has already bookmarked this story.
            "bookmarked": story.storyid in bookmarked_ids,

            # All stories reaching this point are publicly
            # available, so only authentication is required.
            "can_bookmark": request.user.is_authenticated,
        })

    return render(request, "stories/feed.html", {
        "stories": results
    })
