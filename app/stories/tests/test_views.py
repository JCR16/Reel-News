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
        self.factory = RequestFactory()

    @patch("stories.views.render")
    @patch("stories.views.Story.objects.filter")
    def test_feed_empty(self, mock_story_filter, mock_render):
        """Render an empty feed when no published stories exist"""

        mock_story_filter.return_value.order_by.return_value = []

        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = feed(request)

        # Verify that only eligible published stories are requested.
        mock_story_filter.assert_called_once_with(
            status="Published",
            publishedrevisionnum__isnull=False,
        )

        mock_story_filter.return_value.order_by.assert_called_once_with(
            "storyid"
        )

        mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {"stories": []},
        )

        self.assertIs(response, mock_render.return_value)

    @patch("stories.views.render")
    @patch("stories.views.StoryRevision.objects.filter")
    @patch("stories.views.Story.objects.filter")
    def test_feed_with_one_story(
        self,
        mock_story_filter,
        mock_revision_filter,
        mock_render,
    ):
        """Render a published story with its published content"""

        story = MagicMock(spec=Story)
        story.storyid = 1
        story.currentrevisionnum = 1
        story.publishedrevisionnum = 1
        story.status = "Published"
        story.imageurl = "https://example.com/image.jpg"

        revision = MagicMock(spec=StoryRevision)
        revision.headline = "Test Headline"
        revision.summary = "This is a test summary."

        # Simulate database query results.
        mock_story_filter.return_value.order_by.return_value = [
            story
        ]

        mock_revision_filter.return_value.first.return_value = (
            revision
        )

        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = feed(request)

        mock_story_filter.assert_called_once_with(
            status="Published",
            publishedrevisionnum__isnull=False,
        )

        # Verify that the published revision was requested.
        mock_revision_filter.assert_called_once_with(
            storyid_id=1,
            revisionnum=1,
            status="Published",
        )

        mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {
                "stories": [
                    {
                        "id": 1,
                        "headline": "Test Headline",
                        "summary": "This is a test summary.",
                        "image": "https://example.com/image.jpg",
                        "bookmarked": False,
                        "can_bookmark": False,
                    }
                ]
            },
        )

        self.assertIs(response, mock_render.return_value)



class ExpandedFeedViewTests(SimpleTestCase):
    """Expanded Story Feed Views"""

    def start_patch(self, target):
        # Automatically remove patches after each test.
        patcher = patch(f"stories.views.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.factory = RequestFactory()

        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        self.anonymous_user = AnonymousUser()

        # Mock the published story query and its ordering.
        self.mock_story_filter = self.start_patch(
            "Story.objects.filter"
        )

        self.mock_order_by = (
            self.mock_story_filter.return_value.order_by
        )

        self.mock_filter = self.start_patch(
            "StoryRevision.objects.filter"
        )

        self.mock_get_bookmarks = self.start_patch(
            "get_bookmarks"
        )

        self.mock_render = self.start_patch("render")

        # Default to an empty feed and no bookmarks.
        self.mock_order_by.return_value = []

        self.mock_get_bookmarks.return_value.values_list.return_value = []

    # ---------------------------------------------------------
    # Test Helpers
    # ---------------------------------------------------------

    def create_request(self, authenticated=False):
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
        story = MagicMock(spec=Story)

        story.storyid = story_id
        story.status = status
        story.currentrevisionnum = current_revision
        story.publishedrevisionnum = published_revision
        story.imageurl = image

        return story

    def create_revision(self, headline, summary):
        revision = MagicMock(spec=StoryRevision)

        revision.headline = headline
        revision.summary = summary

        return revision

    def configure_feed(self, stories, revisions):
        # Simulate the stories returned by the filtered query.
        self.mock_order_by.return_value = stories

        # Create a separate queryset for each revision lookup.
        querysets = []

        for revision in revisions:
            queryset = MagicMock()
            queryset.first.return_value = revision
            querysets.append(queryset)

        self.mock_filter.side_effect = querysets

    def get_rendered_stories(self):
        context = self.mock_render.call_args.args[2]
        return context["stories"]

    # ---------------------------------------------------------
    # Publication Visibility Tests
    # ---------------------------------------------------------

    def test_feed_filters_published_stories(self):
        """Request only published stories with a published revision"""

        feed(self.create_request())

        # Verify the publication restrictions applied to the query.
        self.mock_story_filter.assert_called_once_with(
            status="Published",
            publishedrevisionnum__isnull=False,
        )

        self.mock_order_by.assert_called_once_with("storyid")

    def test_feed_uses_published_revision(self):
        """Display the published revision instead of the working revision"""

        for current_revision, published_revision in (
            (2, 1),
            (5, 3),
            (10, 7),
        ):
            with self.subTest(
                current_revision=current_revision,
                published_revision=published_revision,
            ):
                self.mock_filter.reset_mock()
                self.mock_render.reset_mock()

                story = self.create_story(
                    story_id=10,
                    current_revision=current_revision,
                    published_revision=published_revision,
                )

                revision = self.create_revision(
                    "Published headline",
                    "Published summary.",
                )

                self.configure_feed([story], [revision])

                feed(self.create_request())

                # The working revision must never be requested.
                self.mock_filter.assert_called_once_with(
                    storyid_id=10,
                    revisionnum=published_revision,
                    status="Published",
                )

                results = self.get_rendered_stories()

                self.assertEqual(len(results), 1)

                self.assertEqual(
                    results[0]["headline"],
                    "Published headline",
                )

                self.assertEqual(
                    results[0]["summary"],
                    "Published summary.",
                )

    def test_feed_requires_published_revision_status(self):
        """Require the referenced revision to have Published status"""

        story = self.create_story(
            story_id=10,
            current_revision=2,
            published_revision=1,
        )

        # Simulate a revision lookup returning no matching
        # published revision.
        self.configure_feed([story], [None])

        feed(self.create_request())

        self.mock_filter.assert_called_once_with(
            storyid_id=10,
            revisionnum=1,
            status="Published",
        )

        self.assertEqual(self.get_rendered_stories(), [])

    def test_feed_omits_story_status(self):
        """Do not pass the redundant story status to the template"""

        story = self.create_story(10)

        revision = self.create_revision(
            "Test headline",
            "Test summary.",
        )

        self.configure_feed([story], [revision])

        feed(self.create_request())

        results = self.get_rendered_stories()

        self.assertEqual(len(results), 1)
        self.assertNotIn("status", results[0])

    # ---------------------------------------------------------
    # Feed Content Tests
    # ---------------------------------------------------------

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

        self.assertEqual(
            self.mock_filter.call_args_list,
            [
                call(
                    storyid_id=10,
                    revisionnum=1,
                    status="Published",
                ),
                call(
                    storyid_id=20,
                    revisionnum=1,
                    status="Published",
                ),
            ],
        )

        self.mock_render.assert_called_once_with(
            request,
            "stories/feed.html",
            {
                "stories": [
                    {
                        "id": 10,
                        "headline": "First headline",
                        "summary": "First summary.",
                        "image": "https://example.com/first.jpg",
                        "bookmarked": False,
                        "can_bookmark": False,
                    },
                    {
                        "id": 20,
                        "headline": "Second headline",
                        "summary": "Second summary.",
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

        self.mock_order_by.assert_called_once_with("storyid")

        results = self.get_rendered_stories()

        self.assertEqual(
            [story["id"] for story in results],
            [10, 20, 30],
        )

    def test_feed_skip_missing_revision(self):
        """Skip a story whose published revision does not exist"""

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

        # A missing revision should not prevent other
        # published stories from being displayed.
        self.assertEqual(
            [story["id"] for story in results],
            [10, 30],
        )

        self.assertEqual(self.mock_filter.call_count, 3)

    def test_feed_all_revisions_missing(self):
        """Return an empty feed when no published revisions exist"""

        stories = [
            self.create_story(10),
            self.create_story(20),
        ]

        self.configure_feed(stories, [None, None])

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

    # ---------------------------------------------------------
    # Bookmark Tests
    # ---------------------------------------------------------

    def test_feed_anonymous_bookmark_behavior(self):
        """Disable bookmark controls for anonymous visitors"""

        story = self.create_story(10)

        revision = self.create_revision(
            "Test headline",
            "Test summary.",
        )

        self.configure_feed([story], [revision])

        feed(self.create_request())

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

        # Include a bookmarked story that is absent from the feed.
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

        # Retrieve bookmarks only once for the entire feed.
        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.mock_get_bookmarks.return_value.values_list.assert_called_once_with(
            "storyid_id",
            flat=True,
        )

    def test_feed_authenticated_empty_feed(self):
        """Handle an authenticated user viewing an empty feed"""

        self.mock_order_by.return_value = []

        request = self.create_request(authenticated=True)

        feed(request)

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
        # Automatically remove patches after each test.
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

        # Create the corresponding published revision.
        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 1
        self.revision.status = "Published"
        self.revision.headline = "Test headline"
        self.revision.summary = "Test summary."

        # Mock story and revision retrieval.
        self.mock_get_object = self.start_patch(
            "get_object_or_404"
        )

        self.mock_get_object.side_effect = [
            self.story,
            self.revision,
        ]

        # Mock source article retrieval.
        self.mock_source_filter = self.start_patch(
            "RevisionArticle.objects.filter"
        )

        self.mock_select_related = (
            self.mock_source_filter.return_value.select_related
        )

        self.mock_order_by = (
            self.mock_select_related.return_value.order_by
        )

        # Default to no source articles.
        self.mock_order_by.return_value = []

        self.mock_render = self.start_patch("render")

    # ---------------------------------------------------------
    # Test Helpers
    # ---------------------------------------------------------

    def create_request(self, story_id=10):
        """Construct a request to the story detail endpoint."""

        url = reverse(
            "story_detail",
            kwargs={"story_id": story_id},
        )

        request = self.factory.get(url)
        request.user = AnonymousUser()

        return request

    def assert_story_lookup(self, story_id=10):
        """Verify the public story eligibility requirements."""

        self.mock_get_object.assert_any_call(
            Story,
            storyid=story_id,
            status__in=("Published", "Archived"),
            publishedrevisionnum__isnull=False,
        )

    def assert_revision_lookup(self, revision_num=1):
        """Verify the published revision lookup."""

        self.mock_get_object.assert_any_call(
            StoryRevision,
            storyid_id=10,
            revisionnum=revision_num,
            status="Published",
        )

    def create_source(
        self,
        title,
        url,
        publisher_name=None,
        bias_category=None,
    ):
        """Create a mock source article and its publisher."""

        source = MagicMock()

        source.articleid.title = title
        source.articleid.link = url

        if publisher_name is not None:
            publisher = MagicMock()
            publisher.name = publisher_name
            publisher.biascategory = bias_category

            source.articleid.publisherid = publisher
        else:
            source.articleid.publisherid = None

        return source

    # ---------------------------------------------------------
    # Story Detail Rendering Tests
    # ---------------------------------------------------------

    def test_story_detail_success(self):
        """Render a published story and its published revision"""

        request = self.create_request()

        response = story_detail(request, story_id=10)

        self.assert_story_lookup()
        self.assert_revision_lookup()

        self.assertEqual(self.mock_get_object.call_count, 2)

        self.mock_render.assert_called_once_with(
            request,
            "stories/detail.html",
            {
                "story": self.story,
                "revision": self.revision,
                "sources": [],
            },
        )

        self.assertIs(
            response,
            self.mock_render.return_value,
        )

    def test_story_detail_archived_story(self):
        """Allow direct access to an archived story"""

        self.story.status = "Archived"

        request = self.create_request()

        response = story_detail(request, story_id=10)

        self.assert_story_lookup()
        self.assert_revision_lookup()

        self.mock_render.assert_called_once_with(
            request,
            "stories/detail.html",
            {
                "story": self.story,
                "revision": self.revision,
                "sources": [],
            },
        )

        self.assertIs(
            response,
            self.mock_render.return_value,
        )

    # ---------------------------------------------------------
    # Publication Visibility Tests
    # ---------------------------------------------------------

    def test_story_detail_public_access_requirements(self):
        """Require an eligible story status and published revision"""

        story_detail(
            self.create_request(),
            story_id=10,
        )

        # Verify that the story eligibility restrictions are
        # applied before retrieving the revision.
        self.assertEqual(
            self.mock_get_object.call_args_list[0],
            call(
                Story,
                storyid=10,
                status__in=("Published", "Archived"),
                publishedrevisionnum__isnull=False,
            ),
        )

    def test_story_detail_uses_published_revision(self):
        """Display published content instead of the working revision"""

        for current_revision, published_revision in (
            (2, 1),
            (5, 3),
            (10, 7),
        ):
            with self.subTest(
                current_revision=current_revision,
                published_revision=published_revision,
            ):
                self.mock_get_object.reset_mock()
                self.mock_source_filter.reset_mock()
                self.mock_render.reset_mock()

                self.story.currentrevisionnum = current_revision
                self.story.publishedrevisionnum = published_revision

                self.revision.revisionnum = published_revision

                self.mock_get_object.side_effect = [
                    self.story,
                    self.revision,
                ]

                request = self.create_request()

                story_detail(request, story_id=10)

                # Verify that the working revision is never requested.
                self.assertEqual(
                    self.mock_get_object.call_args_list,
                    [
                        call(
                            Story,
                            storyid=10,
                            status__in=("Published", "Archived"),
                            publishedrevisionnum__isnull=False,
                        ),
                        call(
                            StoryRevision,
                            storyid_id=10,
                            revisionnum=published_revision,
                            status="Published",
                        ),
                    ],
                )

                # Sources must also belong to the published revision.
                self.mock_source_filter.assert_called_once_with(
                    storyid_id=10,
                    revisionnum=published_revision,
                )

                self.mock_render.assert_called_once_with(
                    request,
                    "stories/detail.html",
                    {
                        "story": self.story,
                        "revision": self.revision,
                        "sources": [],
                    },
                )

    def test_story_detail_requires_published_revision_status(self):
        """Require the referenced revision to have Published status"""

        # Simulate a published pointer that does not reference
        # a revision matching the publication requirements.
        self.mock_get_object.side_effect = [
            self.story,
            Http404("Published revision not found."),
        ]

        with self.assertRaises(Http404):
            story_detail(
                self.create_request(),
                story_id=10,
            )

        self.assert_revision_lookup()

        self.mock_source_filter.assert_not_called()
        self.mock_render.assert_not_called()

    # ---------------------------------------------------------
    # Source Article Tests
    # ---------------------------------------------------------

    def test_story_detail_source_query(self):
        """Retrieve sources associated with the published revision"""

        story_detail(
            self.create_request(),
            story_id=10,
        )

        self.mock_source_filter.assert_called_once_with(
            storyid_id=10,
            revisionnum=1,
        )

        # Retrieve article and publisher information together.
        self.mock_select_related.assert_called_once_with(
            "articleid",
            "articleid__publisherid",
        )

        # Preserve deterministic source ordering.
        self.mock_order_by.assert_called_once_with(
            "articleid_id"
        )

    def test_story_detail_multiple_sources(self):
        """Pass multiple source articles to the detail template"""

        sources = [
            self.create_source(
                "First article",
                "https://example.com/first",
                "First Publisher",
                "Left",
            ),
            self.create_source(
                "Second article",
                "https://example.com/second",
                "Second Publisher",
                "Center",
            ),
            self.create_source(
                "Third article",
                "https://example.com/third",
                "Third Publisher",
                "Right",
            ),
        ]

        self.mock_order_by.return_value = sources

        request = self.create_request()

        story_detail(request, story_id=10)

        self.mock_render.assert_called_once_with(
            request,
            "stories/detail.html",
            {
                "story": self.story,
                "revision": self.revision,
                "sources": sources,
            },
        )

    def test_story_detail_no_sources(self):
        """Render the detail page when no source articles exist"""

        self.mock_order_by.return_value = []

        request = self.create_request()

        response = story_detail(request, story_id=10)

        context = self.mock_render.call_args.args[2]

        self.assertEqual(context["sources"], [])
        self.assertIs(response, self.mock_render.return_value)

    def test_story_detail_source_without_publisher(self):
        """Pass through source articles without publisher information"""

        source = self.create_source(
            "Article without publisher",
            "https://example.com/article",
        )

        self.mock_order_by.return_value = [source]

        story_detail(
            self.create_request(),
            story_id=10,
        )

        context = self.mock_render.call_args.args[2]

        self.assertEqual(context["sources"], [source])

        self.assertIsNone(
            context["sources"][0].articleid.publisherid
        )

    # ---------------------------------------------------------
    # Missing Object and Access Failure Tests
    # ---------------------------------------------------------

    def test_story_detail_nonexistent_story(self):
        """Raise HTTP 404 when the requested story does not exist"""

        self.mock_get_object.side_effect = Http404(
            "Story not found."
        )

        request = self.create_request(story_id=999)

        with self.assertRaises(Http404):
            story_detail(request, story_id=999)

        self.mock_get_object.assert_called_once_with(
            Story,
            storyid=999,
            status__in=("Published", "Archived"),
            publishedrevisionnum__isnull=False,
        )

        # Do not retrieve revisions or sources for a missing story.
        self.mock_source_filter.assert_not_called()
        self.mock_render.assert_not_called()

    def test_story_detail_missing_revision(self):
        """Raise HTTP 404 when the published revision does not exist"""

        self.mock_get_object.side_effect = [
            self.story,
            Http404("Revision not found."),
        ]

        with self.assertRaises(Http404):
            story_detail(
                self.create_request(),
                story_id=10,
            )

        self.assert_story_lookup()
        self.assert_revision_lookup()

        self.assertEqual(self.mock_get_object.call_count, 2)

        # A detail page cannot be rendered without a revision.
        self.mock_source_filter.assert_not_called()
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