
from copy import deepcopy
from unittest.mock import MagicMock, patch

from django.contrib.admin import AdminSite, ModelAdmin
from django.test import SimpleTestCase, RequestFactory

from stories.admin import StoryAdmin
from stories.models import Story


class StoryAdminFieldsetTests(SimpleTestCase):

    def setUp(self):
        self.admin = StoryAdmin(Story, AdminSite())
        self.request = RequestFactory().get("/admin/stories/story/")

        # Representative fieldsets returned by Django's ModelAdmin.
        self.fieldsets = [
            (None, {
                "fields": ("status",)
            }),
            ("Current Revision", {
                "fields": (
                    "editing_revision",
                    "editing_revision_status",
                    "review_feedback",
                )
            }),
            ("Published Revision", {
                "fields": ("publishedrevisionnum",)
            }),
        ]

    # ---------------------------------------------------------
    # Test Helpers
    # ---------------------------------------------------------

    def create_mock_story(
        self,
        current_status="Draft",
        current_revision_num=1,
        published_revision_num=None,
        story_status="Draft",
    ):
        """Create a mock story with configurable revision information."""

        story = MagicMock(spec=Story)

        story.status = story_status
        story.currentrevisionnum = current_revision_num
        story.publishedrevisionnum = published_revision_num

        revision = MagicMock()
        revision.status = current_status

        # Simulate retrieving the current revision.
        story.revisions.filter.return_value.first.return_value = (
            revision if current_status is not None else None
        )

        return story

    def get_fieldsets(self, story=None, can_edit=True):
        """Retrieve fieldsets while mocking Django and permissions."""

        with (
            patch.object(
                ModelAdmin,
                "get_fieldsets",
                return_value=self.fieldsets,
            ),
            patch.object(
                self.admin,
                "has_change_permission",
                return_value=can_edit,
            ),
        ):
            return self.admin.get_fieldsets(self.request, story)

    def get_current_fields(self, fieldsets):
        """Retrieve the fields belonging to the current revision."""

        for name, options in fieldsets:
            if name and name.startswith("Current Revision"):
                return options["fields"]

        self.fail("Current Revision fieldset was not found.")

    # ---------------------------------------------------------
    # Review Feedback Tests
    # ---------------------------------------------------------

    def test_feedback_hidden_for_non_rejected_revisions(self):
        """Non-rejected revisions do not display review feedback."""

        for status in ("Draft", "Published"):
            with self.subTest(status=status):
                story = self.create_mock_story(current_status=status)

                fieldsets = self.get_fieldsets(story)
                fields = self.get_current_fields(fieldsets)

                self.assertNotIn("review_feedback", fields)
                self.assertNotIn("current_review_feedback", fields)

    def test_feedback_editable_for_rejected_revision(self):
        """Editable rejected revisions display the feedback input."""

        story = self.create_mock_story(current_status="Rejected")

        fieldsets = self.get_fieldsets(story, can_edit=True)
        fields = self.get_current_fields(fieldsets)

        self.assertIn("review_feedback", fields)
        self.assertNotIn("current_review_feedback", fields)

    def test_feedback_readonly_for_rejected_revision(self):
        """Read-only rejected revisions display read-only feedback."""

        story = self.create_mock_story(current_status="Rejected")

        fieldsets = self.get_fieldsets(story, can_edit=False)
        fields = self.get_current_fields(fieldsets)

        self.assertNotIn("review_feedback", fields)
        self.assertIn("current_review_feedback", fields)

    def test_feedback_hidden_for_readonly_non_rejected_revisions(self):
        """Read-only non-rejected revisions do not display feedback."""

        for status in ("Draft", "Published"):
            with self.subTest(status=status):
                story = self.create_mock_story(current_status=status)

                fieldsets = self.get_fieldsets(story, can_edit=False)
                fields = self.get_current_fields(fieldsets)

                self.assertNotIn("review_feedback", fields)
                self.assertNotIn("current_review_feedback", fields)

    def test_feedback_field_already_absent(self):
        """Removing an already absent feedback field does not fail."""

        # Reproduce the condition that previously caused a ValueError.
        self.fieldsets[1][1]["fields"] = (
            "editing_revision",
            "editing_revision_status",
        )

        story = self.create_mock_story(current_status="Draft")

        fieldsets = self.get_fieldsets(story)
        fields = self.get_current_fields(fieldsets)

        self.assertNotIn("review_feedback", fields)
        self.assertNotIn("current_review_feedback", fields)

    # ---------------------------------------------------------
    # Editing Permission Tests
    # ---------------------------------------------------------

    def test_editable_story_retains_tracking_fields(self):
        """Editable stories retain stale-form tracking fields."""

        for status in ("Draft", "Rejected", "Published"):
            with self.subTest(status=status):
                story = self.create_mock_story(current_status=status)

                fieldsets = self.get_fieldsets(story, can_edit=True)
                fields = self.get_current_fields(fieldsets)

                self.assertIn("editing_revision", fields)
                self.assertIn("editing_revision_status", fields)

    def test_readonly_story_removes_tracking_fields(self):
        """Read-only stories remove stale-form tracking fields."""

        for status in ("Draft", "Rejected", "Published"):
            with self.subTest(status=status):
                story = self.create_mock_story(current_status=status)

                fieldsets = self.get_fieldsets(story, can_edit=False)
                fields = self.get_current_fields(fieldsets)

                self.assertNotIn("editing_revision", fields)
                self.assertNotIn("editing_revision_status", fields)

    def test_archived_story_with_rejected_revision(self):
        """A read-only archived story displays rejected feedback."""

        story = self.create_mock_story(
            current_status="Rejected",
            current_revision_num=2,
            published_revision_num=1,
            story_status="Archived",
        )

        fieldsets = self.get_fieldsets(story, can_edit=False)
        fields = self.get_current_fields(fieldsets)

        self.assertIn("current_review_feedback", fields)
        self.assertNotIn("review_feedback", fields)
        self.assertNotIn("editing_revision", fields)
        self.assertNotIn("editing_revision_status", fields)

    # ---------------------------------------------------------
    # Fieldset Heading Tests
    # ---------------------------------------------------------

    def test_current_revision_heading_includes_status(self):
        """The current revision heading includes its status."""

        for status in ("Draft", "Rejected", "Published"):
            with self.subTest(status=status):
                story = self.create_mock_story(current_status=status)

                fieldsets = self.get_fieldsets(story)
                headings = [name for name, _ in fieldsets]

                self.assertIn(
                    f"Current Revision ({status})",
                    headings,
                )

    def test_published_revision_heading_includes_number(self):
        """The published revision heading includes its number."""

        story = self.create_mock_story(
            current_revision_num=3,
            published_revision_num=2,
        )

        fieldsets = self.get_fieldsets(story)
        headings = [name for name, _ in fieldsets]

        self.assertIn("Published Revision (2)", headings)

    def test_unpublished_story_heading_displays_none(self):
        """Unpublished stories display None in the published heading."""

        story = self.create_mock_story(
            published_revision_num=None,
        )

        fieldsets = self.get_fieldsets(story)
        headings = [name for name, _ in fieldsets]

        self.assertIn("Published Revision (None)", headings)

    # ---------------------------------------------------------
    # Missing Object and Revision Tests
    # ---------------------------------------------------------

    def test_no_story_returns_original_fieldsets(self):
        """Requests without a story return the original fieldsets."""

        fieldsets = self.get_fieldsets(story=None)

        self.assertEqual(fieldsets, self.fieldsets)

    def test_story_without_current_revision(self):
        """Stories without a current revision hide feedback."""

        story = self.create_mock_story(
            current_status=None,
            current_revision_num=None,
        )

        fieldsets = self.get_fieldsets(story)
        headings = [name for name, _ in fieldsets]
        fields = self.get_current_fields(fieldsets)

        self.assertIn("Current Revision", headings)
        self.assertNotIn("review_feedback", fields)

        # No revision lookup should occur without a revision number.
        story.revisions.filter.assert_not_called()

    def test_current_revision_not_found(self):
        """A missing current revision does not cause an exception."""

        story = self.create_mock_story(
            current_status=None,
            current_revision_num=5,
        )

        fieldsets = self.get_fieldsets(story)
        headings = [name for name, _ in fieldsets]
        fields = self.get_current_fields(fieldsets)

        self.assertIn("Current Revision", headings)
        self.assertNotIn("review_feedback", fields)

        story.revisions.filter.assert_called_once_with(
            revisionnum=5
        )

    # ---------------------------------------------------------
    # Fieldset Configuration Integrity Tests
    # ---------------------------------------------------------

    def test_unrelated_fieldsets_remain_unchanged(self):
        """Unrelated fieldsets are preserved."""

        story = self.create_mock_story()

        fieldsets = self.get_fieldsets(story)

        self.assertEqual(fieldsets[0], self.fieldsets[0])

    def test_original_fieldsets_are_not_modified(self):
        """Dynamic fieldset construction preserves the originals."""

        original_fieldsets = deepcopy(self.fieldsets)

        for status in ("Draft", "Rejected", "Published"):
            for can_edit in (True, False):
                with self.subTest(
                    status=status,
                    can_edit=can_edit,
                ):
                    story = self.create_mock_story(
                        current_status=status
                    )

                    self.get_fieldsets(story, can_edit=can_edit)

                    self.assertEqual(
                        self.fieldsets,
                        original_fieldsets,
                    )

    def test_repeated_requests_do_not_leak_fieldset_changes(self):
        """One request's fieldset changes do not affect later requests."""

        draft_story = self.create_mock_story(
            current_status="Draft"
        )

        rejected_story = self.create_mock_story(
            current_status="Rejected"
        )

        # First request removes feedback and editing fields.
        draft_fieldsets = self.get_fieldsets(
            draft_story,
            can_edit=False,
        )

        # Second request should still receive all editable fields.
        rejected_fieldsets = self.get_fieldsets(
            rejected_story,
            can_edit=True,
        )

        draft_fields = self.get_current_fields(draft_fieldsets)
        rejected_fields = self.get_current_fields(rejected_fieldsets)

        self.assertNotIn("review_feedback", draft_fields)
        self.assertNotIn("editing_revision", draft_fields)

        self.assertIn("review_feedback", rejected_fields)
        self.assertIn("editing_revision", rejected_fields)
        self.assertIn("editing_revision_status", rejected_fields)
        self.assertNotIn("current_review_feedback", rejected_fields)
