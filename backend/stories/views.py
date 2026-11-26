from django.shortcuts import render
from django.shortcuts import get_object_or_404
from .models import Story, StoryRevision, RevisionArticle

from accounts.services.bookmark_manager import get_bookmarks

from .models import Story, StoryRevision

def story_detail(request, story_id):
    story = get_object_or_404(Story, storyid=story_id)

    revision = get_object_or_404(
        StoryRevision,
        storyid_id=story.storyid,
        revisionnum=story.currentrevisionnum
    )

    return render(request, "stories/detail.html", {
        "story": story,
        "revision": revision,
    })

def feed(request):
    stories = Story.objects.order_by("storyid")
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
        revision = StoryRevision.objects.filter(
            storyid_id=story.storyid,
            revisionnum=story.currentrevisionnum
        ).first()

        if revision is None:
            continue

        results.append({
            "id": story.storyid,
            "headline": revision.headline,
            "summary": revision.summary,
            "status": story.status,
            "image": story.imageurl,

            # Whether the user has already bookmarked this story.
            "bookmarked": story.storyid in bookmarked_ids,

            # Only authenticated users can bookmark stories
            # that have a published revision and eligible status.
            "can_bookmark": (
                request.user.is_authenticated
                and story.status in ("Published", "Archived")
                and story.publishedrevisionnum is not None
            ),
        })

    return render(request, "stories/feed.html", {
        "stories": results
    })