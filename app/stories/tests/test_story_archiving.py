# Reel News - Story Archiving Unit Tests
#
# Developed by: Reel News team
# Description: Tests story archiving and restoration using
# mocked database operations without connecting to PostgreSQL.
#
# External libraries:
# - Django SimpleTestCase: Unit testing framework.
# - Python unittest.mock: Mock database queries and model objects.
#
# External code:
# - No third-party source code copied or adapted.

from django.test import SimpleTestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock

from stories.models import Story
from stories.services.story_archiving import archive_story, restore_story


class StoryArchivingTests(SimpleTestCase):

    section_name = "Story Archiving and Restoration"

    def setUp(self):
        # Create a mock story with an existing published revision
        self.story = MagicMock(spec=Story)
        self.story.storyid = 1
        self.story.status = "Published"
        self.story.currentrevisionnum = 2
        self.story.publishedrevisionnum = 1
        self.story.datemodified = None

    @patch("stories.services.story_archiving.timezone.now")
    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_archive_published_story(self, mock_select, mock_now):

        # Simulate retrieving the story from the database
        mock_select.return_value.get.return_value = self.story

        # Provide a predictable modification timestamp
        timestamp = timezone.datetime(
            2026, 11, 25, 12, 0,
            tzinfo=timezone.get_current_timezone()
        )
        mock_now.return_value = timestamp

        # Execute the service without its database transaction wrapper
        result = archive_story.__wrapped__(1)

        # Verify the story was retrieved using its primary key
        mock_select.assert_called_once_with()
        mock_select.return_value.get.assert_called_once_with(pk=1)

        # Verify the story was archived
        self.assertEqual(self.story.status, "Archived")
        self.assertEqual(self.story.datemodified, timestamp)

        # Verify revision pointers were preserved
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertEqual(self.story.publishedrevisionnum, 1)

        # Verify only the intended fields were saved
        self.story.save.assert_called_once_with(
            update_fields=["status", "datemodified"]
        )

        # Verify the service returns the updated story
        self.assertIs(result, self.story)

    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_archive_invalid_status(self, mock_select):

        mock_select.return_value.get.return_value = self.story

        # Test every unsupported publication status
        for status in ("Draft", "Changes Needed", "Archived"):
            with self.subTest(status=status):
                self.story.status = status

                # Verify the operation is rejected
                with self.assertRaisesMessage(
                    ValueError,
                    "Only published stories can be archived."
                ):
                    archive_story.__wrapped__(1)

                # Verify the story remains unchanged
                self.assertEqual(self.story.status, status)
                self.assertIsNone(self.story.datemodified)
                self.story.save.assert_not_called()

    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_archive_without_published_revision(self, mock_select):

        # Simulate a published story with no published revision
        self.story.publishedrevisionnum = None
        mock_select.return_value.get.return_value = self.story

        with self.assertRaisesMessage(
            ValueError,
            "The story has no published revision."
        ):
            archive_story.__wrapped__(1)

        # Verify the story was not modified or saved
        self.assertEqual(self.story.status, "Published")
        self.assertIsNone(self.story.datemodified)
        self.story.save.assert_not_called()

    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_archive_nonexistent_story(self, mock_select):

        # Simulate a database lookup that finds no matching story
        mock_select.return_value.get.side_effect = Story.DoesNotExist

        with self.assertRaises(Story.DoesNotExist):
            archive_story.__wrapped__(999)

        mock_select.return_value.get.assert_called_once_with(pk=999)

    @patch("stories.services.story_archiving.timezone.now")
    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_restore_archived_story(self, mock_select, mock_now):

        # Simulate retrieving an archived story
        self.story.status = "Archived"
        mock_select.return_value.get.return_value = self.story

        # Provide a predictable modification timestamp
        timestamp = timezone.datetime(
            2026, 11, 25, 12, 0,
            tzinfo=timezone.get_current_timezone()
        )
        mock_now.return_value = timestamp

        result = restore_story.__wrapped__(1)

        # Verify the expected database lookup
        mock_select.assert_called_once_with()
        mock_select.return_value.get.assert_called_once_with(pk=1)

        # Verify the story was restored
        self.assertEqual(self.story.status, "Published")
        self.assertEqual(self.story.datemodified, timestamp)

        # Verify revision pointers were preserved
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertEqual(self.story.publishedrevisionnum, 1)

        # Verify only the intended fields were saved
        self.story.save.assert_called_once_with(
            update_fields=["status", "datemodified"]
        )

        self.assertIs(result, self.story)

    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_restore_invalid_status(self, mock_select):

        mock_select.return_value.get.return_value = self.story

        # Test every unsupported publication status
        for status in ("Published", "Draft", "Changes Needed"):
            with self.subTest(status=status):
                self.story.status = status

                with self.assertRaisesMessage(
                    ValueError,
                    "Only archived stories can be restored."
                ):
                    restore_story.__wrapped__(1)

                # Verify the story remains unchanged
                self.assertEqual(self.story.status, status)
                self.assertIsNone(self.story.datemodified)
                self.story.save.assert_not_called()

    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_restore_without_published_revision(self, mock_select):

        # Simulate an archived story with no published revision
        self.story.status = "Archived"
        self.story.publishedrevisionnum = None
        mock_select.return_value.get.return_value = self.story

        with self.assertRaisesMessage(
            ValueError,
            "The story has no published revision."
        ):
            restore_story.__wrapped__(1)

        # Verify the story was not modified or saved
        self.assertEqual(self.story.status, "Archived")
        self.assertIsNone(self.story.datemodified)
        self.story.save.assert_not_called()

    @patch("stories.services.story_archiving.Story.objects.select_for_update")
    def test_restore_nonexistent_story(self, mock_select):

        # Simulate a database lookup that finds no matching story
        mock_select.return_value.get.side_effect = Story.DoesNotExist

        with self.assertRaises(Story.DoesNotExist):
            restore_story.__wrapped__(999)

        mock_select.return_value.get.assert_called_once_with(pk=999)