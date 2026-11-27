import json

from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse, resolve

from accounts.models import Bookmark
from stories.models import Story

from accounts.views import (
    add_bookmark,
    remove_bookmark,
    bookmark_status,
    list_bookmarks,
)

User = get_user_model()


class AddBookmarkViewTests(SimpleTestCase):
    """Add Bookmark Endpoint"""

    def setUp(self):
        self.factory = RequestFactory()

        # Create an authenticated mock user.
        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        self.bookmark = MagicMock(spec=Bookmark)

        # Resolve the endpoint URL using Django's URL configuration.
        self.url = reverse(
            "add_bookmark",
            kwargs={"story_id": 10},
        )

        # Mock the underlying bookmark service.
        patcher = patch("accounts.views.bookmark_story")
        self.mock_bookmark = patcher.start()
        self.addCleanup(patcher.stop)

    def create_request(self):
        # Construct an authenticated POST request.
        request = self.factory.post(self.url)
        request.user = self.user
        return request

    def test_create_new_bookmark(self):
        """Return HTTP 201 when a new bookmark is created"""

        self.mock_bookmark.return_value = (
            self.bookmark,
            True,
        )

        response = add_bookmark(
            self.create_request(),
            story_id=10,
        )

        # Verify that the correct user and story were supplied.
        self.mock_bookmark.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response["Content-Type"],
            "application/json",
        )

        # Verify the complete JSON response.
        self.assertEqual(
            json.loads(response.content),
            {
                "story_id": 10,
                "bookmarked": True,
                "created": True,
            },
        )

    def test_add_existing_bookmark(self):
        """Return HTTP 200 when the bookmark already exists"""

        self.mock_bookmark.return_value = (
            self.bookmark,
            False,
        )

        response = add_bookmark(
            self.create_request(),
            story_id=10,
        )

        self.mock_bookmark.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            {
                "story_id": 10,
                "bookmarked": True,
                "created": False,
            },
        )

    def test_bookmark_nonexistent_story(self):
        """Return HTTP 404 when the story does not exist"""

        self.mock_bookmark.side_effect = Story.DoesNotExist

        response = add_bookmark(
            self.create_request(),
            story_id=10,
        )

        self.mock_bookmark.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 404)

        self.assertEqual(
            json.loads(response.content),
            {
                "error": "Story not found.",
            },
        )

    def test_bookmark_validation_failure(self):
        """Return HTTP 400 when bookmark validation fails"""

        messages = [
            "Authentication is required.",
            "This story is not publicly available.",
            "This story has no published revision.",
        ]

        for message in messages:
            with self.subTest(error=message):

                self.mock_bookmark.reset_mock()

                # Simulate a validation error from the service.
                self.mock_bookmark.side_effect = ValueError(
                    message
                )

                response = add_bookmark(
                    self.create_request(),
                    story_id=10,
                )

                self.mock_bookmark.assert_called_once_with(
                    self.user,
                    10,
                )

                self.assertEqual(response.status_code, 400)

                # Verify that the service's error message is preserved.
                self.assertEqual(
                    json.loads(response.content),
                    {
                        "error": message,
                    },
                )


class RemoveBookmarkViewTests(SimpleTestCase):
    """Remove Bookmark Endpoint"""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        self.url = reverse(
            "remove_bookmark",
            kwargs={"story_id": 10},
        )

        # Mock the underlying bookmark removal service.
        patcher = patch("accounts.views.unbookmark_story")
        self.mock_unbookmark = patcher.start()
        self.addCleanup(patcher.stop)

    def create_request(self):
        request = self.factory.post(self.url)
        request.user = self.user
        return request

    def test_remove_existing_bookmark(self):
        """Return HTTP 200 after removing an existing bookmark"""

        self.mock_unbookmark.return_value = True

        response = remove_bookmark(
            self.create_request(),
            story_id=10,
        )

        self.mock_unbookmark.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            {
                "story_id": 10,
                "bookmarked": False,
                "removed": True,
            },
        )

    def test_remove_nonexistent_bookmark(self):
        """Return HTTP 200 when the bookmark does not exist"""

        self.mock_unbookmark.return_value = False

        response = remove_bookmark(
            self.create_request(),
            story_id=10,
        )

        self.mock_unbookmark.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            {
                "story_id": 10,
                "bookmarked": False,
                "removed": False,
            },
        )


class BookmarkStatusViewTests(SimpleTestCase):
    """Bookmark Status Endpoint"""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        self.url = reverse(
            "bookmark_status",
            kwargs={"story_id": 10},
        )

        # Mock the bookmark status service.
        patcher = patch("accounts.views.is_bookmarked")
        self.mock_is_bookmarked = patcher.start()
        self.addCleanup(patcher.stop)

    def create_request(self):
        request = self.factory.get(self.url)
        request.user = self.user
        return request

    def test_bookmarked_story_status(self):
        """Return the status of a bookmarked story"""

        self.mock_is_bookmarked.return_value = True

        response = bookmark_status(
            self.create_request(),
            story_id=10,
        )

        self.mock_is_bookmarked.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            {
                "story_id": 10,
                "bookmarked": True,
            },
        )

    def test_unbookmarked_story_status(self):
        """Return the status of an unbookmarked story"""

        self.mock_is_bookmarked.return_value = False

        response = bookmark_status(
            self.create_request(),
            story_id=10,
        )

        self.mock_is_bookmarked.assert_called_once_with(
            self.user,
            10,
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            {
                "story_id": 10,
                "bookmarked": False,
            },
        )


class BookmarkListViewTests(SimpleTestCase):
    """Bookmark List Endpoint"""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        self.url = reverse("list_bookmarks")

        # Mock the bookmark retrieval service.
        patcher = patch("accounts.views.get_bookmarks")
        self.mock_get_bookmarks = patcher.start()
        self.addCleanup(patcher.stop)

    def create_request(self):
        request = self.factory.get(self.url)
        request.user = self.user
        return request

    def create_bookmark(
        self,
        story_id,
        status,
        published_revision,
        date_created,
    ):
        # Create a mock story associated with the bookmark.
        story = MagicMock(spec=Story)
        story.pk = story_id
        story.status = status
        story.publishedrevisionnum = published_revision

        # Simulate a newer working revision.
        story.currentrevisionnum = published_revision + 1

        # Create the bookmark record.
        bookmark = MagicMock(spec=Bookmark)
        bookmark.userid = self.user
        bookmark.storyid = story
        bookmark.storyid_id = story_id
        bookmark.datecreated = date_created

        return bookmark

    def test_empty_bookmark_list(self):
        """Return an empty bookmark list"""

        self.mock_get_bookmarks.return_value = []

        response = list_bookmarks(
            self.create_request()
        )

        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            {
                "count": 0,
                "bookmarks": [],
            },
        )

    def test_single_bookmark_list(self):
        """Serialize a single bookmarked story"""

        date_created = datetime(
            2026, 11, 27, 12, 0,
            tzinfo=timezone.utc,
        )

        bookmark = self.create_bookmark(
            story_id=10,
            status="Published",
            published_revision=2,
            date_created=date_created,
        )

        self.mock_get_bookmarks.return_value = [
            bookmark
        ]

        response = list_bookmarks(
            self.create_request()
        )

        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/json",
        )

        # Verify that the published revision is returned,
        # rather than the newer working revision.
        self.assertEqual(
            json.loads(response.content),
            {
                "count": 1,
                "bookmarks": [
                    {
                        "story_id": 10,
                        "story_status": "Published",
                        "published_revision_num": 2,
                        "date_bookmarked": (
                            "2026-11-27T12:00:00+00:00"
                        ),
                    },
                ],
            },
        )

    def test_multiple_bookmark_list(self):
        """Serialize published and archived bookmarks in service order"""

        newer_date = datetime(
            2026, 11, 27, 12, 0,
            tzinfo=timezone.utc,
        )

        older_date = datetime(
            2026, 11, 26, 12, 0,
            tzinfo=timezone.utc,
        )

        published_bookmark = self.create_bookmark(
            story_id=20,
            status="Published",
            published_revision=3,
            date_created=newer_date,
        )

        archived_bookmark = self.create_bookmark(
            story_id=10,
            status="Archived",
            published_revision=1,
            date_created=older_date,
        )

        # Simulate bookmarks already ordered by the service.
        self.mock_get_bookmarks.return_value = [
            published_bookmark,
            archived_bookmark,
        ]

        response = list_bookmarks(
            self.create_request()
        )

        self.mock_get_bookmarks.assert_called_once_with(
            self.user
        )

        self.assertEqual(response.status_code, 200)

        # Verify that both bookmarks are serialized correctly
        # and that the service's ordering is preserved.
        self.assertEqual(
            json.loads(response.content),
            {
                "count": 2,
                "bookmarks": [
                    {
                        "story_id": 20,
                        "story_status": "Published",
                        "published_revision_num": 3,
                        "date_bookmarked": (
                            "2026-11-27T12:00:00+00:00"
                        ),
                    },
                    {
                        "story_id": 10,
                        "story_status": "Archived",
                        "published_revision_num": 1,
                        "date_bookmarked": (
                            "2026-11-26T12:00:00+00:00"
                        ),
                    },
                ],
            },
        )


class BookmarkAuthenticationTests(SimpleTestCase):
    """Bookmark Endpoint Authentication"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = AnonymousUser()

        # Mock every bookmark service.
        self.mock_add = self.start_patch("bookmark_story")
        self.mock_remove = self.start_patch("unbookmark_story")
        self.mock_status = self.start_patch("is_bookmarked")
        self.mock_list = self.start_patch("get_bookmarks")

    def start_patch(self, target):
        patcher = patch(f"accounts.views.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def assert_login_redirect(self, response, requested_url):
        # Verify that authentication is required.
        self.assertEqual(response.status_code, 302)

        # Parse the redirect destination and query parameters.
        destination = urlsplit(response["Location"])

        # Verify that the user was redirected to the login page.
        self.assertEqual(
            destination.path,
            reverse("login"),
        )

        # Verify that the original endpoint was preserved
        # in Django's next parameter.
        self.assertEqual(
            parse_qs(destination.query).get("next"),
            [requested_url],
        )

        # Authentication must prevent all bookmark service calls.
        self.mock_add.assert_not_called()
        self.mock_remove.assert_not_called()
        self.mock_status.assert_not_called()
        self.mock_list.assert_not_called()

    def test_anonymous_add_bookmark(self):
        """Require authentication to add bookmarks"""

        url = reverse(
            "add_bookmark",
            kwargs={"story_id": 10},
        )

        request = self.factory.post(url)
        request.user = self.user

        response = add_bookmark(
            request,
            story_id=10,
        )

        self.assert_login_redirect(response, url)

    def test_anonymous_remove_bookmark(self):
        """Require authentication to remove bookmarks"""

        url = reverse(
            "remove_bookmark",
            kwargs={"story_id": 10},
        )

        request = self.factory.post(url)
        request.user = self.user

        response = remove_bookmark(
            request,
            story_id=10,
        )

        self.assert_login_redirect(response, url)

    def test_anonymous_bookmark_status(self):
        """Require authentication to check bookmark status"""

        url = reverse(
            "bookmark_status",
            kwargs={"story_id": 10},
        )

        request = self.factory.get(url)
        request.user = self.user

        response = bookmark_status(
            request,
            story_id=10,
        )

        self.assert_login_redirect(response, url)

    def test_anonymous_bookmark_list(self):
        """Require authentication to retrieve bookmarks"""

        url = reverse("list_bookmarks")

        request = self.factory.get(url)
        request.user = self.user

        response = list_bookmarks(request)

        self.assert_login_redirect(response, url)


class BookmarkHTTPMethodTests(SimpleTestCase):
    """Bookmark Endpoint HTTP Method Restrictions"""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        # Mock every bookmark service.
        self.mock_add = self.start_patch("bookmark_story")
        self.mock_remove = self.start_patch("unbookmark_story")
        self.mock_status = self.start_patch("is_bookmarked")
        self.mock_list = self.start_patch("get_bookmarks")

    def start_patch(self, target):
        patcher = patch(f"accounts.views.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def assert_method_restrictions(
        self,
        view,
        url,
        allowed_method,
        rejected_methods,
        **kwargs,
    ):
        # Test each unsupported HTTP method independently.
        for method in rejected_methods:
            with self.subTest(method=method):

                # Construct a request using the unsupported method.
                request = self.factory.generic(
                    method,
                    url,
                )

                request.user = self.user

                response = view(request, **kwargs)

                # Verify that Django rejected the HTTP method.
                self.assertEqual(
                    response.status_code,
                    405,
                )

                # Verify that the response identifies the allowed method.
                self.assertEqual(
                    response["Allow"],
                    allowed_method,
                )

                # Unsupported methods must not reach the services.
                self.mock_add.assert_not_called()
                self.mock_remove.assert_not_called()
                self.mock_status.assert_not_called()
                self.mock_list.assert_not_called()

    def test_add_bookmark_http_methods(self):
        """Restrict bookmark creation to POST requests"""

        self.assert_method_restrictions(
            view=add_bookmark,
            url=reverse(
                "add_bookmark",
                kwargs={"story_id": 10},
            ),
            allowed_method="POST",
            rejected_methods=[
                "GET",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
            ],
            story_id=10,
        )

    def test_remove_bookmark_http_methods(self):
        """Restrict bookmark removal to POST requests"""

        self.assert_method_restrictions(
            view=remove_bookmark,
            url=reverse(
                "remove_bookmark",
                kwargs={"story_id": 10},
            ),
            allowed_method="POST",
            rejected_methods=[
                "GET",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
            ],
            story_id=10,
        )

    def test_bookmark_status_http_methods(self):
        """Restrict bookmark status lookups to GET requests"""

        self.assert_method_restrictions(
            view=bookmark_status,
            url=reverse(
                "bookmark_status",
                kwargs={"story_id": 10},
            ),
            allowed_method="GET",
            rejected_methods=[
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
            ],
            story_id=10,
        )

    def test_bookmark_list_http_methods(self):
        """Restrict bookmark retrieval to GET requests"""

        self.assert_method_restrictions(
            view=list_bookmarks,
            url=reverse("list_bookmarks"),
            allowed_method="GET",
            rejected_methods=[
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
            ],
        )


class BookmarkURLTests(SimpleTestCase):
    """Bookmark URL Routing"""

    def test_add_bookmark_url(self):
        """Resolve the bookmark creation endpoint"""

        url = reverse(
            "add_bookmark",
            kwargs={"story_id": 10},
        )

        match = resolve(url)

        self.assertIs(match.func, add_bookmark)
        self.assertEqual(match.url_name, "add_bookmark")
        self.assertEqual(
            match.kwargs,
            {"story_id": 10},
        )

    def test_remove_bookmark_url(self):
        """Resolve the bookmark removal endpoint"""

        url = reverse(
            "remove_bookmark",
            kwargs={"story_id": 10},
        )

        match = resolve(url)

        self.assertIs(match.func, remove_bookmark)
        self.assertEqual(match.url_name, "remove_bookmark")
        self.assertEqual(
            match.kwargs,
            {"story_id": 10},
        )

    def test_bookmark_status_url(self):
        """Resolve the bookmark status endpoint"""

        url = reverse(
            "bookmark_status",
            kwargs={"story_id": 10},
        )

        match = resolve(url)

        self.assertIs(match.func, bookmark_status)
        self.assertEqual(match.url_name, "bookmark_status")
        self.assertEqual(
            match.kwargs,
            {"story_id": 10},
        )

    def test_bookmark_list_url(self):
        """Resolve the bookmark list endpoint"""

        url = reverse("list_bookmarks")

        match = resolve(url)

        self.assertIs(match.func, list_bookmarks)
        self.assertEqual(match.url_name, "list_bookmarks")
        self.assertEqual(match.kwargs, {})