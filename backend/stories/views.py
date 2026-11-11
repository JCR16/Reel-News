# Reel News - Story API
#
# Developed by: Reel News team
# Description: Retrieves stories and their current revisions from
# PostgreSQL and formats the results for the React frontend.
#
# External libraries:
# - Django REST Framework: API request handling and responses
#
# External code:
# - No third-party source code was copied or adapted.
# - Django REST Framework is used through its public API.

from django.shortcuts import render
from django.shortcuts import get_object_or_404

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
        })

    return render(request, "stories/feed.html", {
        "stories": results
    })