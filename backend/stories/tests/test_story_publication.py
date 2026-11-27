from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from stories.models import Story, StoryRevision
from stories.services.story_publication import (
    approve_revision,
    reject_revision,
    update_review_feedback,
)


class StoryApprovalTests(SimpleTestCase):
    """Story Revision Approval"""

    def setUp(self):
        # Create a mock story with an unpublished Draft revision.
        self.story = MagicMock(spec=Story)
        self.story.pk = 1
        self.story.status = "Draft"
        self.story.currentrevisionnum = 1
        self.story.publishedrevisionnum = None

        # Create the mock current revision.
        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 1
        self.revision.status = "Draft"
        self.revision.reviewfeedback = None

        # Return the mock revision when the service retrieves
        # the story's current revision.
        self.story.revisions.filter.return_value.first.return_value = (
            self.revision
        )

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_unpublished_story(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Approve an unpublished Draft story"""

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Simulate retrieving the IDs of the revision's source articles.
        mock_revision_article.objects.filter.return_value.values_list.return_value = [
            10, 20
        ]

        # Execute the service without opening a database transaction.
        result = approve_revision.__wrapped__(
            story_id=1,
            expected_revision_num=1,
        )

        # Verify that the correct story was retrieved with a lock.
        mock_story.objects.select_for_update.assert_called_once_with()
        mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=1
        )

        # Verify that the correct revision was retrieved.
        self.story.revisions.filter.assert_called_once_with(
            revisionnum=1
        )

        # Verify that the revision was published.
        self.assertEqual(self.revision.status, "Published")
        self.revision.save.assert_called_once_with(
            update_fields=["status"]
        )

        # Verify that the story was published.
        self.assertEqual(self.story.status, "Published")
        self.assertEqual(self.story.publishedrevisionnum, 1)
        self.assertEqual(self.story.currentrevisionnum, 1)

        self.story.save.assert_called_once_with(
            update_fields=["publishedrevisionnum", "status"]
        )

        # Verify that the published revision's articles were retrieved.
        mock_revision_article.objects.filter.assert_called_once_with(
            storyid=self.story,
            revisionnum=1,
        )

        mock_revision_article.objects.filter.return_value.values_list.assert_called_once_with(
            "articleid_id",
            flat=True,
        )

        # Verify that article text cleanup was scheduled.
        mock_on_commit.assert_called_once()

        # Verify that the service returned the approved revision.
        self.assertIs(result, self.revision)

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_new_revision(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Approve a new revision of an already published story"""

        # Simulate a published story with a newer Draft revision.
        self.story.status = "Published"
        self.story.publishedrevisionnum = 1
        self.story.currentrevisionnum = 2
        self.revision.revisionnum = 2

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Simulate retrieving the new revision's source articles.
        mock_revision_article.objects.filter.return_value.values_list.return_value = [
            20, 30
        ]

        # Approve the second revision.
        result = approve_revision.__wrapped__(
            story_id=1,
            expected_revision_num=2,
        )

        # Verify that the correct revision was retrieved.
        self.story.revisions.filter.assert_called_once_with(
            revisionnum=2
        )

        # Verify that the new revision was published.
        self.assertEqual(self.revision.status, "Published")
        self.revision.save.assert_called_once_with(
            update_fields=["status"]
        )

        # Verify that the published pointer advanced while
        # the story remained Published.
        self.assertEqual(self.story.status, "Published")
        self.assertEqual(self.story.publishedrevisionnum, 2)
        self.assertEqual(self.story.currentrevisionnum, 2)

        self.story.save.assert_called_once_with(
            update_fields=["publishedrevisionnum", "status"]
        )

        # Verify that cleanup targets the newly published revision.
        mock_revision_article.objects.filter.assert_called_once_with(
            storyid=self.story,
            revisionnum=2,
        )

        mock_on_commit.assert_called_once()

        # Verify that the newly published revision was returned.
        self.assertIs(result, self.revision)

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_archived_story(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Reject approval of an archived story"""

        # Simulate an archived story with an unpublished Draft revision.
        self.story.status = "Archived"
        self.story.publishedrevisionnum = 1
        self.story.currentrevisionnum = 2
        self.revision.revisionnum = 2

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Verify that approval raises the expected error.
        with self.assertRaisesMessage(
            ValueError,
            "Archived stories must be restored before approving revisions.",
        ):
            approve_revision.__wrapped__(
                story_id=1,
                expected_revision_num=2,
            )

        # Verify that the story and revision remain unchanged.
        self.assertEqual(self.story.status, "Archived")
        self.assertEqual(self.story.publishedrevisionnum, 1)
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertEqual(self.revision.status, "Draft")

        # Verify that the operation stopped before retrieving the revision.
        self.story.revisions.filter.assert_not_called()

        # Verify that no changes were saved.
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

        # Verify that article text cleanup was not scheduled.
        mock_revision_article.objects.filter.assert_not_called()
        mock_on_commit.assert_not_called()

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_stale_revision(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Reject approval with a stale revision number"""

        # Simulate a newer revision being generated after
        # an administrator opened the previous revision.
        self.story.currentrevisionnum = 2
        self.revision.revisionnum = 2

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Attempt to approve revision 1 when revision 2 is current.
        with self.assertRaisesMessage(
            ValueError,
            "The current revision has changed. Please review it again.",
        ):
            approve_revision.__wrapped__(
                story_id=1,
                expected_revision_num=1,
            )

        # Verify that the story and revision remain unchanged.
        self.assertEqual(self.story.status, "Draft")
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertIsNone(self.story.publishedrevisionnum)
        self.assertEqual(self.revision.status, "Draft")

        # Verify that the operation stopped before retrieving
        # or modifying the current revision.
        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

        # Verify that article text cleanup was not scheduled.
        mock_revision_article.objects.filter.assert_not_called()
        mock_on_commit.assert_not_called()

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_without_expected_revision(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Reject approval without an expected revision number"""

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Attempt approval without identifying the reviewed revision.
        with self.assertRaisesMessage(
            ValueError,
            "The current revision has changed. Please review it again.",
        ):
            approve_revision.__wrapped__(
                story_id=1,
                expected_revision_num=None,
            )

        # Verify that the story and revision remain unchanged.
        self.assertEqual(self.story.status, "Draft")
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertIsNone(self.story.publishedrevisionnum)
        self.assertEqual(self.revision.status, "Draft")

        # Verify that no revision was retrieved or modified.
        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

        # Verify that article text cleanup was not scheduled.
        mock_revision_article.objects.filter.assert_not_called()
        mock_on_commit.assert_not_called()

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_missing_current_revision(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Reject approval when the current revision is missing"""

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Simulate the current revision not being found.
        self.story.revisions.filter.return_value.first.return_value = None

        # Attempt to approve the missing revision.
        with self.assertRaisesMessage(
            ValueError,
            "Only Draft revisions can be approved.",
        ):
            approve_revision.__wrapped__(
                story_id=1,
                expected_revision_num=1,
            )

        # Verify that the service attempted to retrieve the revision.
        self.story.revisions.filter.assert_called_once_with(
            revisionnum=1
        )

        # Verify that the story remains unchanged.
        self.assertEqual(self.story.status, "Draft")
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertIsNone(self.story.publishedrevisionnum)

        # Verify that no changes were saved.
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

        # Verify that article text cleanup was not scheduled.
        mock_revision_article.objects.filter.assert_not_called()
        mock_on_commit.assert_not_called()

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_non_draft_revision(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Reject approval of non-Draft revisions"""

        # Test each revision status that is ineligible for approval.
        for status in ["Published", "Rejected"]:
            with self.subTest(status=status):

                # Reset mocks to isolate each scenario.
                self.setUp()
                mock_story.reset_mock()
                mock_revision_article.reset_mock()
                mock_on_commit.reset_mock()

                # Simulate a revision that is not a Draft.
                self.revision.status = status

                if status == "Published":
                    self.story.status = "Published"
                    self.story.publishedrevisionnum = 1
                else:
                    self.story.status = "Changes Needed"
                    self.revision.reviewfeedback = "Needs improvement."

                # Record the original story state and feedback.
                original_status = self.story.status
                original_published = self.story.publishedrevisionnum
                original_feedback = self.revision.reviewfeedback

                # Simulate retrieving and locking the story.
                mock_story.objects.select_for_update.return_value.get.return_value = (
                    self.story
                )

                # Attempt to approve the non-Draft revision.
                with self.assertRaisesMessage(
                    ValueError,
                    "Only Draft revisions can be approved.",
                ):
                    approve_revision.__wrapped__(
                        story_id=1,
                        expected_revision_num=1,
                    )

                # Verify that the story and revision remain unchanged.
                self.assertEqual(self.story.status, original_status)
                self.assertEqual(
                    self.story.publishedrevisionnum,
                    original_published,
                )
                self.assertEqual(self.story.currentrevisionnum, 1)
                self.assertEqual(self.revision.status, status)
                self.assertEqual(
                    self.revision.reviewfeedback,
                    original_feedback,
                )

                # Verify that no changes were saved.
                self.story.save.assert_not_called()
                self.revision.save.assert_not_called()

                # Verify that cleanup was not scheduled.
                mock_revision_article.objects.filter.assert_not_called()
                mock_on_commit.assert_not_called()

    @patch("stories.services.story_publication.transaction.on_commit")
    @patch("stories.services.story_publication.RevisionArticle")
    @patch("stories.services.story_publication.Story")
    def test_approve_nonexistent_story(
        self, mock_story, mock_revision_article, mock_on_commit
    ):
        """Handle approval of a nonexistent story"""

        # Simulate the database raising an exception because
        # the requested story does not exist.
        mock_story.objects.select_for_update.return_value.get.side_effect = (
            Story.DoesNotExist
        )

        # Verify that the service propagates the exception.
        with self.assertRaises(Story.DoesNotExist):
            approve_revision.__wrapped__(
                story_id=999,
                expected_revision_num=1,
            )

        # Verify that the service attempted to retrieve
        # and lock the correct story.
        mock_story.objects.select_for_update.assert_called_once_with()

        mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=999
        )

        # Verify that no revision was retrieved or modified.
        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

        # Verify that article text cleanup was not scheduled.
        mock_revision_article.objects.filter.assert_not_called()
        mock_on_commit.assert_not_called()


class StoryRejectionTests(SimpleTestCase):
    """Story Revision Rejection"""

    def setUp(self):
        # Create a mock unpublished story with a Draft revision.
        self.story = MagicMock(spec=Story)
        self.story.pk = 1
        self.story.status = "Draft"
        self.story.currentrevisionnum = 1
        self.story.publishedrevisionnum = None

        # Create the mock current revision.
        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 1
        self.revision.status = "Draft"
        self.revision.reviewfeedback = None

        # Return the current revision when requested.
        self.story.revisions.filter.return_value.first.return_value = (
            self.revision
        )

    @patch("stories.services.story_publication.Story")
    def test_reject_unpublished_story(self, mock_story):
        """Reject an unpublished Draft story"""

        # Simulate retrieving and locking the story.
        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Reject the revision using feedback containing extra whitespace.
        result = reject_revision.__wrapped__(
            story_id=1,
            feedback="  Needs more neutral language.  ",
            expected_revision_num=1,
        )

        # Verify that the correct story was retrieved with a lock.
        mock_story.objects.select_for_update.assert_called_once_with()
        mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=1
        )

        # Verify that the correct revision was retrieved.
        self.story.revisions.filter.assert_called_once_with(
            revisionnum=1
        )

        # Verify that the revision was rejected and feedback was trimmed.
        self.assertEqual(self.revision.status, "Rejected")
        self.assertEqual(
            self.revision.reviewfeedback,
            "Needs more neutral language.",
        )

        self.revision.save.assert_called_once_with(
            update_fields=["status", "reviewfeedback"]
        )

        # Verify that the unpublished story now requires changes.
        self.assertEqual(self.story.status, "Changes Needed")
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertIsNone(self.story.publishedrevisionnum)

        self.story.save.assert_called_once_with(
            update_fields=["status"]
        )

        # Verify that the rejected revision was returned.
        self.assertIs(result, self.revision)

    @patch("stories.services.story_publication.Story")
    def test_reject_published_story_revision(self, mock_story):
        """Reject a new revision of an already published story"""

        # Simulate a published story with a newer Draft revision.
        self.story.status = "Published"
        self.story.publishedrevisionnum = 1
        self.story.currentrevisionnum = 2
        self.revision.revisionnum = 2

        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Reject the newer revision.
        result = reject_revision.__wrapped__(
            story_id=1,
            feedback="Additional sources are required.",
            expected_revision_num=2,
        )

        # Verify that the correct revision was retrieved.
        self.story.revisions.filter.assert_called_once_with(
            revisionnum=2
        )

        # Verify that the new revision was rejected.
        self.assertEqual(self.revision.status, "Rejected")
        self.assertEqual(
            self.revision.reviewfeedback,
            "Additional sources are required.",
        )

        self.revision.save.assert_called_once_with(
            update_fields=["status", "reviewfeedback"]
        )

        # Verify that the existing publication remains unchanged.
        self.assertEqual(self.story.status, "Published")
        self.assertEqual(self.story.publishedrevisionnum, 1)
        self.assertEqual(self.story.currentrevisionnum, 2)

        # No story-level changes need to be saved.
        self.story.save.assert_not_called()

        self.assertIs(result, self.revision)

    @patch("stories.services.story_publication.Story")
    def test_reject_archived_story(self, mock_story):
        """Prevent rejection of an archived story"""

        # Simulate an archived story with a newer Draft revision.
        self.story.status = "Archived"
        self.story.publishedrevisionnum = 1
        self.story.currentrevisionnum = 2
        self.revision.revisionnum = 2

        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Verify that archived stories cannot be modified.
        with self.assertRaisesMessage(
            ValueError,
            "Archived stories must be restored before rejecting revisions.",
        ):
            reject_revision.__wrapped__(
                story_id=1,
                feedback="Needs improvement.",
                expected_revision_num=2,
            )

        # Verify that the original state was preserved.
        self.assertEqual(self.story.status, "Archived")
        self.assertEqual(self.story.publishedrevisionnum, 1)
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertEqual(self.revision.status, "Draft")
        self.assertIsNone(self.revision.reviewfeedback)

        # Verify that the operation stopped before modifying anything.
        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

    @patch("stories.services.story_publication.Story")
    def test_reject_stale_revision(self, mock_story):
        """Prevent rejection with a stale revision number"""

        # Simulate a newer revision being generated.
        self.story.currentrevisionnum = 2
        self.revision.revisionnum = 2

        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Attempt to reject the previous revision.
        with self.assertRaisesMessage(
            ValueError,
            "The current revision has changed. Please review it again.",
        ):
            reject_revision.__wrapped__(
                story_id=1,
                feedback="Needs improvement.",
                expected_revision_num=1,
            )

        # Verify that the newer revision remains unchanged.
        self.assertEqual(self.story.status, "Draft")
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertIsNone(self.story.publishedrevisionnum)
        self.assertEqual(self.revision.status, "Draft")
        self.assertIsNone(self.revision.reviewfeedback)

        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

    @patch("stories.services.story_publication.Story")
    def test_reject_without_expected_revision(self, mock_story):
        """Prevent rejection without an expected revision number"""

        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Attempt rejection without identifying the reviewed revision.
        with self.assertRaisesMessage(
            ValueError,
            "The current revision has changed. Please review it again.",
        ):
            reject_revision.__wrapped__(
                story_id=1,
                feedback="Needs improvement.",
                expected_revision_num=None,
            )

        # Verify that the original state was preserved.
        self.assertEqual(self.story.status, "Draft")
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertIsNone(self.story.publishedrevisionnum)
        self.assertEqual(self.revision.status, "Draft")
        self.assertIsNone(self.revision.reviewfeedback)

        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

    @patch("stories.services.story_publication.Story")
    def test_reject_missing_current_revision(self, mock_story):
        """Prevent rejection when the current revision is missing"""

        mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Simulate the current revision not being found.
        self.story.revisions.filter.return_value.first.return_value = None

        with self.assertRaisesMessage(
            ValueError,
            "Only Draft revisions can be rejected.",
        ):
            reject_revision.__wrapped__(
                story_id=1,
                feedback="Needs improvement.",
                expected_revision_num=1,
            )

        # Verify that the service attempted to retrieve the revision.
        self.story.revisions.filter.assert_called_once_with(
            revisionnum=1
        )

        # Verify that the story remains unchanged.
        self.assertEqual(self.story.status, "Draft")
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertIsNone(self.story.publishedrevisionnum)

        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()

    @patch("stories.services.story_publication.Story")
    def test_reject_non_draft_revision(self, mock_story):
        """Prevent rejection of non-Draft revisions"""

        # Test each revision status that is ineligible for rejection.
        for status in ["Published", "Rejected"]:
            with self.subTest(status=status):

                # Reset mocks to isolate each scenario.
                self.setUp()
                mock_story.reset_mock()

                self.revision.status = status

                if status == "Published":
                    self.story.status = "Published"
                    self.story.publishedrevisionnum = 1
                else:
                    self.story.status = "Changes Needed"
                    self.revision.reviewfeedback = "Original feedback."

                # Record the original state.
                original_status = self.story.status
                original_published = self.story.publishedrevisionnum
                original_feedback = self.revision.reviewfeedback

                mock_story.objects.select_for_update.return_value.get.return_value = (
                    self.story
                )

                # Attempt to reject the non-Draft revision.
                with self.assertRaisesMessage(
                    ValueError,
                    "Only Draft revisions can be rejected.",
                ):
                    reject_revision.__wrapped__(
                        story_id=1,
                        feedback="Replacement feedback.",
                        expected_revision_num=1,
                    )

                # Verify that the original state and feedback were preserved.
                self.assertEqual(self.story.status, original_status)
                self.assertEqual(
                    self.story.publishedrevisionnum,
                    original_published,
                )
                self.assertEqual(self.story.currentrevisionnum, 1)
                self.assertEqual(self.revision.status, status)
                self.assertEqual(
                    self.revision.reviewfeedback,
                    original_feedback,
                )

                self.story.save.assert_not_called()
                self.revision.save.assert_not_called()

    @patch("stories.services.story_publication.Story")
    def test_reject_invalid_feedback(self, mock_story):
        """Prevent rejection without valid review feedback"""

        # Test missing, empty, and whitespace-only feedback.
        for feedback in [None, "", "   ", "\t\n"]:
            with self.subTest(feedback=feedback):

                # Reset mocks to isolate each scenario.
                self.setUp()
                mock_story.reset_mock()

                mock_story.objects.select_for_update.return_value.get.return_value = (
                    self.story
                )

                # Verify that meaningful feedback is required.
                with self.assertRaisesMessage(
                    ValueError,
                    "Review feedback is required.",
                ):
                    reject_revision.__wrapped__(
                        story_id=1,
                        feedback=feedback,
                        expected_revision_num=1,
                    )

                # Verify that invalid feedback did not modify anything.
                self.assertEqual(self.story.status, "Draft")
                self.assertEqual(self.story.currentrevisionnum, 1)
                self.assertIsNone(self.story.publishedrevisionnum)
                self.assertEqual(self.revision.status, "Draft")
                self.assertIsNone(self.revision.reviewfeedback)

                self.story.save.assert_not_called()
                self.revision.save.assert_not_called()

    @patch("stories.services.story_publication.Story")
    def test_reject_nonexistent_story(self, mock_story):
        """Handle rejection of a nonexistent story"""

        # Simulate the requested story not existing.
        mock_story.objects.select_for_update.return_value.get.side_effect = (
            Story.DoesNotExist
        )

        # Verify that the service propagates the exception.
        with self.assertRaises(Story.DoesNotExist):
            reject_revision.__wrapped__(
                story_id=999,
                feedback="Needs improvement.",
                expected_revision_num=1,
            )

        # Verify that the correct story was requested with a lock.
        mock_story.objects.select_for_update.assert_called_once_with()
        mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=999
        )

        # Verify that no additional operations occurred.
        self.story.revisions.filter.assert_not_called()
        self.story.save.assert_not_called()
        self.revision.save.assert_not_called()