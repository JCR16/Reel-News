from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Story, StoryRevision


@api_view(["GET"])
def get_stories(request):
    stories = Story.objects.all()
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
        })

    return Response(results)
