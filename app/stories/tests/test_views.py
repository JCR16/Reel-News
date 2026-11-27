from django.test import SimpleTestCase, RequestFactory
from unittest.mock import patch, MagicMock, call
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import Http404
from django.urls import reverse, resolve

from stories.models import Story, StoryRevision
from stories.views import feed, story_detail

User = get_user_model()


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
        mock_story.publishedrevisionnum = 1
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


class ExpandedFeedViewTests(SimpleTestCase):
    """Expanded Story Feed Views"""

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test.
        patcher = patch(f"stories.views.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.factory = RequestFactory()

        # Create authenticated and unauthenticated users.
        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        self.anonymous_user = AnonymousUser()

        # Mock database queries, bookmark retrieval, and rendering.
        self.mock_order_by = self.start_patch(
            "Story.objects.order_by"
        )

        self.mock_filter = self.start_patch(
            "StoryRevision.objects.filter"
        )

        self.mock_get_bookmarks = self.start_patch(
            "get_bookmarks"
        )

        self.mock_render = self.start_patch("render")

        # Create default empty query results.
        self.mock_order_by.return_value = []

        self.mock_get_bookmarks.return_value.values_list.return_value = []

    def create_request(self, authenticated=False):
        # Construct a GET request with the appropriate user.
        request = self.factory.get("/")

        request.user = (
            self.user
            if authenticated
            else self.anonymous_user
        )

        return request

    def create_story(
        self,
        story_id,
        status="Published",
        current_revision=1,
        published_revision=1,
        image=None,
    ):
        # Create a mock story with explicitly defined fields.
        story = MagicMock(spec=Story)

        story.storyid = story_id
        story.status = status
        story.currentrevisionnum = current_revision
        story.publishedrevisionnum = published_revision
        story.imageurl = image

        return story

    def create_revision(self, headline, summary):
        # Create a mock revision containing generated content.
        revision = MagicMock(spec=StoryRevision)

        revision.headline = headline
        revision.summary = summary

        return revision

    def configure_feed(self, stories, revisions):
        # Configure the stories returned by the feed query.
        self.mock_order_by.return_value = stories

        # Create a separate queryset for each revision lookup.
        querysets = []

        for revision in revisions:
            queryset = MagicMock()
            queryset.first.return_value = revision
            querysets.append(queryset)

        self.mock_filter.side_effect = querysets

    def get_rendered_stories(self):
        # Retrieve the story list passed to the template.
        context = self.mock_render.call_args.args[2]
        return context["stories"]

    def test_feed_multiple_stories(self):
        """Render multiple stories with their corresponding content"""

        stories = [
            self.create_story(
                story_id=10,
                image="https://example.com/first.jpg",
            ),
            self.create_story(
                story_id=20,
                image="https://example.com/second.jpg",
            ),
        ]

        revisions = [
            self.create_revision(
                "First headline",
                "First summary.",
            ),
            self.create_revision(
                "Second headline",
                "Second summary.",
            ),
        ]

        self.configure_feed(stories, revisions)

        request = self.create_request()
        response = feed(request)

        # Verify that each story's revision was retrieved.
        self.assertEqual(
            self.mock_filter.call_args_list,
            [
                call(storyid_id=10, revisionnum=1),
                call(storyid_id=20, revisionnum=1),
            ],
        )

        # Verify that each story receives its own content.
        self.mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {
                "stories": [
                    {
                        "id": 10,
                        "headline": "First headline",
                        "summary": "First summary.",
                        "status": "Published",
                        "image": "https://example.com/first.jpg",
                        "bookmarked": False,
                        "can_bookmark": False,
                    },
                    {
                        "id": 20,
                        "headline": "Second headline",
                        "summary": "Second summary.",
                        "status": "Published",
                        "image": "https://example.com/second.jpg",
                        "bookmarked": False,
                        "can_bookmark": False,
                    },
                ],
            },
        )

        self.assertIs(response, self.mock_render.return_value)

    def test_feed_story_ordering(self):
        """Preserve the story ordering returned by the database"""

        stories = [
            self.create_story(10),
            self.create_story(20),
            self.create_story(30),
        ]

        revisions = [
            self.create_revision("First", "First summary."),
            self.create_revision("Second", "Second summary."),
            self.create_revision("Third", "Third summary."),
        ]

        self.configure_feed(stories, revisions)

        feed(self.create_request())

        # Verify that the feed requests stories in ID order.
        self.mock_order_by.assert_called_once_with("storyid")

        results = self.get_rendered_stories()

        # Verify that the template receives stories in query order.
        self.assertEqual(
            [story["id"] for story in results],
            [10, 20, 30],
        )

    def test_feed_skip_missing_revision(self):
        """Skip a story whose requested revision does not exist"""

        stories = [
            self.create_story(10),
            self.create_story(20),
            self.create_story(30),
        ]

        revisions = [
            self.create_revision("First", "First summary."),
            None,
            self.create_revision("Third", "Third summary."),
        ]

        self.configure_feed(stories, revisions)

        feed(self.create_request())

        results = self.get_rendered_stories()

        # The missing revision should not prevent other stories
        # from being displayed.
        self.assertEqual(
            [story["id"] for story in results],
            [10, 30],
        )

        self.assertEqual(self.mock_filter.call_count, 3)

    def test_feed_all_revisions_missing(self):
        """Return an empty feed when no revisions exist"""

        stories = [
            self.create_story(10),
            self.create_story(20),
        ]

        self.configure_feed(
            stories,
            [None, None],
        )

        request = self.create_request()

        feed(request)

        self.mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {"stories": []},
        )

        self.assertEqual(self.mock_filter.call_count, 2)

    def test_feed_story_without_image(self):
        """Render a story without an associated image"""

        story = self.create_story(
            story_id=10,
            image=None,
        )

        revision = self.create_revision(
            "Test headline",
            "Test summary.",
        )

        self.configure_feed([story], [revision])

        feed(self.create_request())

        results = self.get_rendered_stories()

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["image"])

    def test_feed_anonymous_bookmark_behavior(self):
        """Disable bookmark controls for anonymous visitors"""

        story = self.create_story(10)

        revision = self.create_revision(
            "Test headline",
            "Test summary.",
        )

        self.configure_feed([story], [revision])

        feed(self.create_request())

        # Anonymous users must not trigger bookmark queries.
        self.mock_get_bookmarks.assert_not_called()

        results = self.get_rendered_stories()

        self.assertIs(results[0]["bookmarked"], False)
        self.assertIs(results[0]["can_bookmark"], False)

    def test_feed_authenticated_bookmarked_story(self):
        """Identify an authenticated user's bookmarked story"""

        story = self.create_story(10)

        revision = self.create_revision(
            "Test headline",
            "Test summary.",
        )

        self.configure_feed([story], [revision])

        # Simulate the user having bookmarked this story.
        self.mock_get_bookmarks.return_value.values_list.return_value = [
            10
        ]

        feed(self.create_request(authenticated=True))

        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.mock_get_bookmarks.return_value.values_list.assert_called_once_with(
            "storyid_id",
            flat=True,
        )

        results = self.get_rendered_stories()

        self.assertIs(results[0]["bookmarked"], True)
        self.assertIs(results[0]["can_bookmark"], True)

    def test_feed_authenticated_unbookmarked_story(self):
        """Identify a story the authenticated user has not bookmarked"""

        story = self.create_story(10)

        revision = self.create_revision(
            "Test headline",
            "Test summary.",
        )

        self.configure_feed([story], [revision])

        # Simulate the user having no bookmarks.
        self.mock_get_bookmarks.return_value.values_list.return_value = []

        feed(self.create_request(authenticated=True))

        results = self.get_rendered_stories()

        self.assertIs(results[0]["bookmarked"], False)
        self.assertIs(results[0]["can_bookmark"], True)

    def test_feed_multiple_bookmark_states(self):
        """Assign independent bookmark states to multiple stories"""

        stories = [
            self.create_story(10),
            self.create_story(20),
            self.create_story(30),
        ]

        revisions = [
            self.create_revision("First", "First summary."),
            self.create_revision("Second", "Second summary."),
            self.create_revision("Third", "Third summary."),
        ]

        self.configure_feed(stories, revisions)

        # The user has bookmarked stories 10 and 30,
        # plus a story that is not present in the feed.
        self.mock_get_bookmarks.return_value.values_list.return_value = [
            10, 30, 999
        ]

        feed(self.create_request(authenticated=True))

        results = self.get_rendered_stories()

        self.assertEqual(
            [story["bookmarked"] for story in results],
            [True, False, True],
        )

        self.assertEqual(
            [story["can_bookmark"] for story in results],
            [True, True, True],
        )

        # Bookmarks should be retrieved once for the entire feed,
        # rather than performing a separate lookup for each story.
        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.mock_get_bookmarks.return_value.values_list.assert_called_once_with(
            "storyid_id",
            flat=True,
        )

    def test_feed_bookmark_eligibility(self):
        """Enforce publication requirements for bookmark controls"""

        scenarios = [
            ("Published", 1, True),
            ("Archived", 1, True),
            ("Published", None, False),
            ("Archived", None, False),
            ("Draft", None, False),
            ("Changes Needed", None, False),
            ("Draft", 1, False),
            ("Unknown", 1, False),
        ]

        for status, published_revision, expected in scenarios:
            with self.subTest(
                status=status,
                published_revision=published_revision,
            ):

                # Reset call history between scenarios.
                self.mock_render.reset_mock()
                self.mock_get_bookmarks.reset_mock()
                self.mock_order_by.reset_mock()
                self.mock_filter.reset_mock()

                story = self.create_story(
                    story_id=10,
                    status=status,
                    published_revision=published_revision,
                )

                revision = self.create_revision(
                    "Test headline",
                    "Test summary.",
                )

                self.configure_feed([story], [revision])

                feed(
                    self.create_request(authenticated=True)
                )

                results = self.get_rendered_stories()

                # Verify the eligibility of the bookmark control.
                self.assertIs(
                    results[0]["can_bookmark"],
                    expected,
                )

                self.assertIs(
                    results[0]["bookmarked"],
                    False,
                )

    def test_feed_authenticated_empty_feed(self):
        """Handle an authenticated user viewing an empty feed"""

        self.mock_order_by.return_value = []

        request = self.create_request(authenticated=True)

        feed(request)

        # The current implementation retrieves bookmarks
        # even when the feed contains no stories.
        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.mock_filter.assert_not_called()

        self.mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {"stories": []},
        )


class StoryDetailViewTests(SimpleTestCase):
    """Story Detail Views"""

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test.
        patcher = patch(f"stories.views.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.factory = RequestFactory()

        # Create a mock published story.
        self.story = MagicMock(spec=Story)
        self.story.storyid = 10
        self.story.status = "Published"
        self.story.currentrevisionnum = 1
        self.story.publishedrevisionnum = 1

        # Create the corresponding revision.
        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 1
        self.revision.headline = "Test headline"
        self.revision.summary = "Test summary."

        # Mock object retrieval and template rendering.
        self.mock_get_object = self.start_patch(
            "get_object_or_404"
        )

        self.mock_render = self.start_patch("render")

        # Return the story followed by its revision.
        self.mock_get_object.side_effect = [
            self.story,
            self.revision,
        ]

    def create_request(self, story_id=10):
        # Construct a request to the story detail endpoint.
        url = reverse(
            "story_detail",
            kwargs={"story_id": story_id},
        )

        request = self.factory.get(url)
        request.user = AnonymousUser()

        return request

    def test_story_detail_success(self):
        """Render an existing story and its revision"""

        request = self.create_request()

        response = story_detail(
            request,
            story_id=10,
        )

        # Verify that the story and revision were retrieved.
        self.assertEqual(
            self.mock_get_object.call_args_list,
            [
                call(
                    Story,
                    storyid=10,
                ),
                call(
                    StoryRevision,
                    storyid_id=10,
                    revisionnum=1,
                ),
            ],
        )

        # Verify that both objects were passed to the template.
        self.mock_render.assert_called_once_with(
            request,
            "stories/detail.html",
            {
                "story": self.story,
                "revision": self.revision,
            },
        )

        self.assertIs(
            response,
            self.mock_render.return_value,
        )

    def test_story_detail_nonexistent_story(self):
        """Raise HTTP 404 when the requested story does not exist"""

        # Simulate get_object_or_404 failing on the story lookup.
        self.mock_get_object.side_effect = Http404(
            "Story not found."
        )

        request = self.create_request(story_id=999)

        with self.assertRaises(Http404):
            story_detail(
                request,
                story_id=999,
            )

        # The revision must not be retrieved without a story.
        self.mock_get_object.assert_called_once_with(
            Story,
            storyid=999,
        )

        self.mock_render.assert_not_called()

    def test_story_detail_missing_revision(self):
        """Raise HTTP 404 when the requested revision does not exist"""

        # Simulate a successful story lookup followed by
        # an unsuccessful revision lookup.
        self.mock_get_object.side_effect = [
            self.story,
            Http404("Revision not found."),
        ]

        request = self.create_request()

        with self.assertRaises(Http404):
            story_detail(
                request,
                story_id=10,
            )

        self.assertEqual(
            self.mock_get_object.call_args_list,
            [
                call(
                    Story,
                    storyid=10,
                ),
                call(
                    StoryRevision,
                    storyid_id=10,
                    revisionnum=1,
                ),
            ],
        )

        # A detail page cannot be rendered without a revision.
        self.mock_render.assert_not_called()


class StoryURLTests(SimpleTestCase):
    """Story View URL Routing"""

    def test_story_detail_url(self):
        """Resolve the story detail endpoint"""

        url = reverse(
            "story_detail",
            kwargs={"story_id": 10},
        )

        match = resolve(url)

        # Verify that the URL resolves to the correct view.
        self.assertIs(match.func, story_detail)

        self.assertEqual(
            match.url_name,
            "story_detail",
        )

        # Verify that the story ID is passed as an integer.
        self.assertEqual(
            match.kwargs,
            {"story_id": 10},
        )

    def test_feed_url(self):
        """Resolve the story feed endpoint"""

        url = reverse("feed")

        match = resolve(url)

        self.assertIs(match.func, feed)
        self.assertEqual(match.url_name, "feed")
        self.assertEqual(match.kwargs, {})