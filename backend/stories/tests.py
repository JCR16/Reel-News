from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch, MagicMock

from .views import get_stories


class StoryAPITests(SimpleTestCase):

    @patch("stories.views.Story.objects.order_by")
    def test_get_stories_empty(self, mock_order_by):
        # Simulate an empty database
        mock_order_by.return_value = []

        # Create a fake GET request
        factory = APIRequestFactory()
        request = factory.get("/api/stories/")

        # Call the API view
        response = get_stories(request)


    @patch("stories.views.StoryRevision.objects.filter")
    @patch("stories.views.Story.objects.order_by")
    def test_get_stories_with_one_story(self, mock_order_by, mock_filter):

        # Create a fake story
        mock_story = MagicMock()
        mock_story.storyid = 1
        mock_story.currentrevisionnum = 1
        mock_story.status = "published"
        mock_story.imageurl = "https://example.com/image.jpg"

        # Create a fake story revision
        mock_revision = MagicMock()
        mock_revision.headline = "Test Headline"
        mock_revision.summary = "This is a test summary."

        # Simulate the database returning our fake story
        mock_order_by.return_value = [mock_story]

        # Simulate finding the story's current revision
        mock_filter.return_value.first.return_value = mock_revision

        # Simulate an HTTP GET request
        factory = APIRequestFactory()
        request = factory.get("/api/stories/")

        # Call the actual Django API view
        response = get_stories(request)

        # Verify the response
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, [{
            "id": 1,
            "headline": "Test Headline",
            "summary": "This is a test summary.",
            "status": "published",
            "image": "https://example.com/image.jpg"
        }])

        # Verify Django looked up the correct revision