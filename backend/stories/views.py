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

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import render

from .models import Story, StoryRevision

def feed(request):
    return render(request, "stories/feed.html")

@api_view(["GET"])
def get_stories(request):
    stories = Story.objects.order_by("storyid") # Could use ("-datemodified","-storyid") to order by most recently modified stories first
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

    return Response(results)
