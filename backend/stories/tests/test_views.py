# Reel News - Story View Unit Tests
#
# Developed by: Reel News team
# Description: Tests Django story views using mocked database
# queries without connecting to PostgreSQL.
#
# External libraries:
# - Django SimpleTestCase: Unit testing framework.
# - Django RequestFactory: Simulated HTTP requests.
# - Python unittest.mock: Mock database queries and model objects.
#
# External code:
# - No third-party source code copied or adapted.

from django.test import SimpleTestCase, RequestFactory
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import AnonymousUser

from stories.views import feed


class FeedViewTests(SimpleTestCase):

    section_name = "Story Feed Views"

    def setUp(self):
        # Create a request factory for each test
        self.factory = RequestFactory()

    @patch("stories.views.render")
    @patch("stories.views.Story.objects.order_by")
    def test_feed_empty(self, mock_order_by, mock_render):

        # Simulate an empty database
        mock_order_by.return_value = []

        # Create a fake GET request
        request = self.factory.get("/")

        # Simulate an unauthenticated visitor because RequestFactory
        # does not execute Django's authentication middleware.
        request.user = AnonymousUser()

        # Call the feed view
        response = feed(request)

        # Verify the expected database query was called
        mock_order_by.assert_called_once_with("storyid")

        # Verify the template receives an empty story list
        mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {"stories": []}
        )

        # Verify the view returns the rendering result
        self.assertIs(response, mock_render.return_value)

    @patch("stories.views.render")
    @patch("stories.views.StoryRevision.objects.filter")
    @patch("stories.views.Story.objects.order_by")
    def test_feed_with_one_story(
        self, mock_order_by, mock_filter, mock_render
    ):

        # Create a fake story
        mock_story = MagicMock()
        mock_story.storyid = 1
        mock_story.currentrevisionnum = 1
        mock_story.status = "Published"
        mock_story.imageurl = "https://example.com/image.jpg"

        # Create a fake story revision
        mock_revision = MagicMock()
        mock_revision.headline = "Test Headline"
        mock_revision.summary = "This is a test summary."

        # Simulate database query results
        mock_order_by.return_value = [mock_story]
        mock_filter.return_value.first.return_value = mock_revision

        # Create a fake GET request
        request = self.factory.get("/")

        # Simulate an unauthenticated visitor because RequestFactory
        # does not execute Django's authentication middleware.
        request.user = AnonymousUser()

        # Call the feed view
        response = feed(request)

        # Verify the correct revision was requested
        mock_filter.assert_called_once_with(
            storyid_id=1,
            revisionnum=1
        )

        # Verify the correct story data is passed to the template
        mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {
                "stories": [
                    {
                        "id": 1,
                        "headline": "Test Headline",
                        "summary": "This is a test summary.",
                        "status": "Published",
                        "image": "https://example.com/image.jpg",
                        "bookmarked": False,
                        "can_bookmark": False,
                    }
                ]
            }
        )

        # Verify the view returns the rendering result
        self.assertIs(response, mock_render.return_value)