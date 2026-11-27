from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from accounts.models import Bookmark
from stories.models import Story

from accounts.services.bookmark_manager import (
    bookmark_story,
    unbookmark_story,
    is_bookmarked,
    get_bookmarks,
)

User = get_user_model()


class BookmarkCreationTests(SimpleTestCase):
    """Bookmark Creation"""

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test.
        patcher = patch(f"accounts.services.bookmark_manager.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        # Create an authenticated mock user.
        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        # Create a publicly accessible story.
        self.story = MagicMock(spec=Story)
        self.story.pk = 10
        self.story.status = "Published"
        self.story.currentrevisionnum = 2
        self.story.publishedrevisionnum = 1

        # Create a mock bookmark.
        self.bookmark = MagicMock(spec=Bookmark)
        self.bookmark.userid = self.user
        self.bookmark.storyid = self.story

        # Mock the database models.
        self.mock_story = self.start_patch("Story")
        self.mock_bookmark = self.start_patch("Bookmark")

        # Configure successful default responses.
        self.mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        self.mock_bookmark.objects.get_or_create.return_value = (
            self.bookmark,
            True,
        )

    def test_create_bookmark(self):
        """Create a bookmark for a published story"""

        result = bookmark_story.__wrapped__(
            self.user,
            10,
        )

        # Verify that the story was locked and retrieved.
        self.mock_story.objects.select_for_update.assert_called_once_with()

        self.mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=10
        )

        # Verify that the bookmark belongs to the correct user and story.
        self.mock_bookmark.objects.get_or_create.assert_called_once_with(
            userid=self.user,
            storyid=self.story,
        )

        # Verify that a newly created bookmark was returned.
        bookmark, created = result

        self.assertIs(bookmark, self.bookmark)
        self.assertTrue(created)

        # Bookmarking must not modify the story's editorial state.
        self.assertEqual(self.story.status, "Published")
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertEqual(self.story.publishedrevisionnum, 1)

        self.story.save.assert_not_called()

    def test_reuse_existing_bookmark(self):
        """Reuse an existing bookmark without creating a duplicate"""

        # False indicates that the bookmark already exists.
        self.mock_bookmark.objects.get_or_create.return_value = (
            self.bookmark,
            False,
        )

        bookmark, created = bookmark_story.__wrapped__(
            self.user,
            10,
        )

        self.mock_bookmark.objects.get_or_create.assert_called_once_with(
            userid=self.user,
            storyid=self.story,
        )

        # Verify that the existing bookmark was returned.
        self.assertIs(bookmark, self.bookmark)
        self.assertFalse(created)

    def test_bookmark_archived_story(self):
        """Allow bookmarking an archived story"""

        # Archived stories remain publicly accessible.
        self.story.status = "Archived"

        bookmark, created = bookmark_story.__wrapped__(
            self.user,
            10,
        )

        self.mock_bookmark.objects.get_or_create.assert_called_once_with(
            userid=self.user,
            storyid=self.story,
        )

        self.assertIs(bookmark, self.bookmark)
        self.assertTrue(created)

        # Bookmarking must not restore the archived story.
        self.assertEqual(self.story.status, "Archived")
        self.story.save.assert_not_called()

    def test_bookmark_unauthenticated_user(self):
        """Prevent unauthenticated users from creating bookmarks"""

        user = AnonymousUser()

        with self.assertRaisesMessage(
            ValueError,
            "Authentication is required.",
        ):
            bookmark_story.__wrapped__(user, 10)

        # Authentication must be checked before database access.
        self.mock_story.objects.select_for_update.assert_not_called()
        self.mock_bookmark.objects.get_or_create.assert_not_called()

    def test_bookmark_unavailable_story(self):
        """Prevent bookmarking stories that are not publicly available"""

        for status in ["Draft", "Changes Needed", "Unknown"]:
            with self.subTest(status=status):

                self.story.status = status

                # Reset call history between scenarios.
                self.mock_story.reset_mock()
                self.mock_bookmark.reset_mock()

                with self.assertRaisesMessage(
                    ValueError,
                    "This story is not publicly available.",
                ):
                    bookmark_story.__wrapped__(
                        self.user,
                        10,
                    )

                # The story must be retrieved before checking its status.
                self.mock_story.objects.select_for_update.assert_called_once_with()

                # No bookmark should be created.
                self.mock_bookmark.objects.get_or_create.assert_not_called()

                self.story.save.assert_not_called()

    def test_bookmark_missing_published_revision(self):
        """Prevent bookmarking stories without a published revision"""

        # Test both publicly accessible story statuses.
        for status in ["Published", "Archived"]:
            with self.subTest(status=status):

                self.story.status = status
                self.story.publishedrevisionnum = None

                self.mock_story.reset_mock()
                self.mock_bookmark.reset_mock()

                with self.assertRaisesMessage(
                    ValueError,
                    "This story has no published revision.",
                ):
                    bookmark_story.__wrapped__(
                        self.user,
                        10,
                    )

                self.mock_bookmark.objects.get_or_create.assert_not_called()

                self.story.save.assert_not_called()

    def test_bookmark_nonexistent_story(self):
        """Handle bookmarking a nonexistent story"""

        # Simulate the requested story not existing.
        self.mock_story.objects.select_for_update.return_value.get.side_effect = (
            Story.DoesNotExist
        )

        with self.assertRaises(Story.DoesNotExist):
            bookmark_story.__wrapped__(
                self.user,
                999,
            )

        self.mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=999
        )

        # A bookmark cannot be created without an existing story.
        self.mock_bookmark.objects.get_or_create.assert_not_called()

    def test_bookmark_creation_operation_order(self):
        """Bookmark creation operation order"""

        # Track calls across both database models.
        operations = MagicMock()

        operations.attach_mock(
            self.mock_story.objects.select_for_update,
            "lock_story",
        )

        operations.attach_mock(
            self.mock_bookmark.objects.get_or_create,
            "create_bookmark",
        )

        bookmark_story.__wrapped__(
            self.user,
            10,
        )

        # Verify that the story was locked before bookmark creation.
        self.assertEqual(
            operations.mock_calls,
            [
                call.lock_story(),
                call.lock_story().get(pk=10),
                call.create_bookmark(
                    userid=self.user,
                    storyid=self.story,
                ),
            ],
        )


class BookmarkRemovalTests(SimpleTestCase):
    """Bookmark Removal"""

    def setUp(self):
        # Create an authenticated mock user.
        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        # Mock the Bookmark model.
        patcher = patch(
            "accounts.services.bookmark_manager.Bookmark"
        )

        self.mock_bookmark = patcher.start()
        self.addCleanup(patcher.stop)

        # Create a mock queryset representing the user's bookmark.
        self.bookmarks = MagicMock()

        self.mock_bookmark.objects.filter.return_value = (
            self.bookmarks
        )

    def test_remove_existing_bookmark(self):
        """Remove an existing bookmark"""

        # Simulate one bookmark being deleted.
        self.bookmarks.delete.return_value = (
            1,
            {"accounts.Bookmark": 1},
        )

        result = unbookmark_story(
            self.user,
            10,
        )

        # Verify that deletion was restricted to this user and story.
        self.mock_bookmark.objects.filter.assert_called_once_with(
            userid=self.user,
            storyid_id=10,
        )

        self.bookmarks.delete.assert_called_once_with()

        self.assertIs(result, True)

    def test_remove_nonexistent_bookmark(self):
        """Handle removal of a nonexistent bookmark"""

        # Simulate no matching bookmark being found.
        self.bookmarks.delete.return_value = (0, {})

        result = unbookmark_story(
            self.user,
            10,
        )

        self.mock_bookmark.objects.filter.assert_called_once_with(
            userid=self.user,
            storyid_id=10,
        )

        self.bookmarks.delete.assert_called_once_with()

        # Removing a nonexistent bookmark should return False.
        self.assertIs(result, False)

    def test_remove_bookmark_unauthenticated_user(self):
        """Prevent unauthenticated users from removing bookmarks"""

        user = AnonymousUser()

        with self.assertRaisesMessage(
            ValueError,
            "Authentication is required.",
        ):
            unbookmark_story(user, 10)

        # No database operations should occur.
        self.mock_bookmark.objects.filter.assert_not_called()
        self.bookmarks.delete.assert_not_called()


class BookmarkStatusTests(SimpleTestCase):
    """Bookmark Status"""

    def setUp(self):
        # Create an authenticated mock user.
        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        # Mock the Bookmark model.
        patcher = patch(
            "accounts.services.bookmark_manager.Bookmark"
        )

        self.mock_bookmark = patcher.start()
        self.addCleanup(patcher.stop)

        # Create a mock queryset for bookmark lookups.
        self.bookmarks = MagicMock()

        self.mock_bookmark.objects.filter.return_value = (
            self.bookmarks
        )

    def test_existing_bookmark_status(self):
        """Return True when a story is bookmarked"""

        self.bookmarks.exists.return_value = True

        result = is_bookmarked(
            self.user,
            10,
        )

        # Verify that only this user's bookmark was examined.
        self.mock_bookmark.objects.filter.assert_called_once_with(
            userid=self.user,
            storyid_id=10,
        )

        self.bookmarks.exists.assert_called_once_with()

        self.assertIs(result, True)

    def test_nonexistent_bookmark_status(self):
        """Return False when a story is not bookmarked"""

        self.bookmarks.exists.return_value = False

        result = is_bookmarked(
            self.user,
            10,
        )

        self.mock_bookmark.objects.filter.assert_called_once_with(
            userid=self.user,
            storyid_id=10,
        )

        self.bookmarks.exists.assert_called_once_with()

        self.assertIs(result, False)

    def test_bookmark_status_unauthenticated_user(self):
        """Prevent unauthenticated bookmark status lookups"""

        user = AnonymousUser()

        with self.assertRaisesMessage(
            ValueError,
            "Authentication is required.",
        ):
            is_bookmarked(user, 10)

        # No bookmark lookup should be performed.
        self.mock_bookmark.objects.filter.assert_not_called()
        self.bookmarks.exists.assert_not_called()


class BookmarkRetrievalTests(SimpleTestCase):
    """Bookmark Retrieval"""

    def setUp(self):
        # Create an authenticated mock user.
        self.user = MagicMock(spec=User)
        self.user.pk = 1
        self.user.is_authenticated = True

        # Mock the Bookmark model.
        patcher = patch(
            "accounts.services.bookmark_manager.Bookmark"
        )

        self.mock_bookmark = patcher.start()
        self.addCleanup(patcher.stop)

        # Create mock querysets for each query stage.
        self.filtered_bookmarks = MagicMock()
        self.related_bookmarks = MagicMock()
        self.ordered_bookmarks = MagicMock()

        # Configure the queryset chain.
        self.mock_bookmark.objects.filter.return_value = (
            self.filtered_bookmarks
        )

        self.filtered_bookmarks.select_related.return_value = (
            self.related_bookmarks
        )

        self.related_bookmarks.order_by.return_value = (
            self.ordered_bookmarks
        )

    def test_retrieve_user_bookmarks(self):
        """Retrieve only publicly accessible bookmarks belonging to the user"""

        result = get_bookmarks(self.user)

        # Verify that only the authenticated user's bookmarks
        # associated with publicly accessible stories are retrieved.
        self.mock_bookmark.objects.filter.assert_called_once_with(
            userid=self.user,
            storyid__status__in=("Published", "Archived"),
            storyid__publishedrevisionnum__isnull=False,
        )

        # Verify that the associated story is retrieved efficiently.
        self.filtered_bookmarks.select_related.assert_called_once_with(
            "storyid"
        )

        # Verify that bookmarks are ordered from newest to oldest.
        self.related_bookmarks.order_by.assert_called_once_with(
            "-datecreated",
            "storyid_id",
        )

        # Verify that the resulting queryset was returned.
        self.assertIs(result, self.ordered_bookmarks)

    def test_bookmark_retrieval_operation_order(self):
        """Bookmark retrieval query construction order"""

        operations = MagicMock()

        operations.attach_mock(
            self.mock_bookmark.objects.filter,
            "filter_bookmarks",
        )

        operations.attach_mock(
            self.filtered_bookmarks.select_related,
            "select_story",
        )

        operations.attach_mock(
            self.related_bookmarks.order_by,
            "order_bookmarks",
        )

        result = get_bookmarks(self.user)

        # Verify the complete query construction sequence.
        self.assertEqual(
            operations.mock_calls,
            [
                call.filter_bookmarks(
                    userid=self.user,
                    storyid__status__in=("Published", "Archived"),
                    storyid__publishedrevisionnum__isnull=False,
                ),
                call.select_story("storyid"),
                call.order_bookmarks(
                    "-datecreated",
                    "storyid_id",
                ),
            ],
        )

        self.assertIs(result, self.ordered_bookmarks)

    def test_retrieve_bookmarks_unauthenticated_user(self):
        """Prevent unauthenticated users from retrieving bookmarks"""

        user = AnonymousUser()

        with self.assertRaisesMessage(
            ValueError,
            "Authentication is required.",
        ):
            get_bookmarks(user)

        # Authentication must be checked before constructing the query.
        self.mock_bookmark.objects.filter.assert_not_called()

        self.filtered_bookmarks.select_related.assert_not_called()
        self.related_bookmarks.order_by.assert_not_called()