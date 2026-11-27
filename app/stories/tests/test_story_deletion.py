# Reel News - Story Deletion Unit Tests
#
# Developed by: Reel News team
# Description: Tests story deletion eligibility and permanent
# deletion using mocked database operations without connecting
# to PostgreSQL.
#
# External libraries:
# - Django SimpleTestCase: Unit testing framework.
# - Python unittest.mock: Mock database queries and model objects.
#
# External code:
# - No third-party source code copied or adapted.

from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock, call
from django.db import models
from accounts.models import Bookmark

from stories.models import Story, ArticleText
from stories.services.story_deletion import (
    can_delete_story,
    delete_story,
)


class StoryDeletionEligibilityTests(SimpleTestCase):

    section_name = "Story Deletion Eligibility"

    def setUp(self):
        # Create a mock story for eligibility testing
        self.story = MagicMock(spec=Story)

    def test_unpublished_stories_can_be_deleted(self):

        # Unpublished drafts and stories requiring changes
        # should be eligible for permanent deletion
        self.story.publishedrevisionnum = None

        for status in ("Draft", "Changes Needed"):
            with self.subTest(status=status):
                self.story.status = status

                self.assertTrue(can_delete_story(self.story))

    def test_previously_published_stories_cannot_be_deleted(self):

        # Stories with a published revision must be archived
        # before they can be permanently deleted
        self.story.publishedrevisionnum = 1

        for status in ("Draft", "Changes Needed"):
            with self.subTest(status=status):
                self.story.status = status

                self.assertFalse(can_delete_story(self.story))

    def test_published_stories_cannot_be_deleted(self):

        self.story.status = "Published"

        # Published stories cannot be deleted regardless
        # of whether their published revision pointer exists
        for revision in (None, 1):
            with self.subTest(published_revision=revision):
                self.story.publishedrevisionnum = revision

                self.assertFalse(can_delete_story(self.story))

    def test_archived_stories_can_be_deleted(self):

        self.story.status = "Archived"

        # Archived stories are eligible for deletion regardless
        # of whether their published revision pointer exists
        for revision in (None, 1):
            with self.subTest(published_revision=revision):
                self.story.publishedrevisionnum = revision

                self.assertTrue(can_delete_story(self.story))

    def test_unrecognized_status_cannot_be_deleted(self):

        # Unknown publication statuses should be rejected
        self.story.status = "Unknown"

        for revision in (None, 1):
            with self.subTest(published_revision=revision):
                self.story.publishedrevisionnum = revision

                self.assertFalse(can_delete_story(self.story))


class StoryDeletionTests(SimpleTestCase):

    section_name = "Permanent Story Deletion"

    def setUp(self):
        # Create a mock archived story with existing revisions
        self.story = MagicMock(spec=Story)
        self.story.storyid = 1
        self.story.status = "Archived"
        self.story.currentrevisionnum = 2
        self.story.publishedrevisionnum = 1

        # Patch each model used by the deletion service
        module = "stories.services.story_deletion"

        self.mock_story = self.start_patch(f"{module}.Story")
        self.mock_revision = self.start_patch(f"{module}.StoryRevision")
        self.mock_story_tag = self.start_patch(f"{module}.StoryTag")
        self.mock_revision_article = self.start_patch(
            f"{module}.RevisionArticle"
        )
        self.mock_article = self.start_patch(f"{module}.Article")
        self.mock_article_author = self.start_patch(
            f"{module}.ArticleAuthor"
        )
        self.mock_article_tag = self.start_patch(f"{module}.ArticleTag")

        # Simulate retrieving the story from the database
        self.mock_story.objects.select_for_update.return_value.get.return_value = (
            self.story
        )

        # Preserve the actual model's DoesNotExist exception
        self.mock_story.DoesNotExist = Story.DoesNotExist

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test
        patcher = patch(target)
        self.addCleanup(patcher.stop)

        return patcher.start()

    def test_delete_ineligible_story(self):

        # Simulate a published story that cannot be deleted
        self.story.status = "Published"

        with self.assertRaisesMessage(
            ValueError,
            "Only unpublished drafts, stories requiring changes, "
            "and archived stories can be permanently deleted."
        ):
            delete_story.__wrapped__(1)

        # Verify revision pointers remain unchanged
        self.assertEqual(self.story.currentrevisionnum, 2)
        self.assertEqual(self.story.publishedrevisionnum, 1)

        # Verify the story was not modified or deleted
        self.story.save.assert_not_called()
        self.story.delete.assert_not_called()

        # Verify no related records were queried for cleanup
        self.mock_revision.objects.filter.assert_not_called()
        self.mock_story_tag.objects.filter.assert_not_called()
        self.mock_revision_article.objects.filter.assert_not_called()
        self.mock_article.objects.filter.assert_not_called()
        self.mock_article_author.objects.filter.assert_not_called()
        self.mock_article_tag.objects.filter.assert_not_called()

    def test_delete_nonexistent_story(self):

        # Simulate a lookup for a story that does not exist
        self.mock_story.objects.select_for_update.return_value.get.side_effect = (
            Story.DoesNotExist
        )

        with self.assertRaises(Story.DoesNotExist):
            delete_story.__wrapped__(999)

        # Verify the correct story ID was requested
        self.mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=999
        )

        # Verify no deletion operations were attempted
        self.story.save.assert_not_called()
        self.story.delete.assert_not_called()
        self.mock_revision_article.objects.filter.assert_not_called()
        self.mock_article.objects.filter.assert_not_called()

    def configure_article_queries(self, article_ids, orphaned_ids):

        # Simulate collecting articles from all story revisions
        self.mock_revision_article.objects.filter.return_value \
            .values_list.return_value.distinct.return_value = article_ids

        # Create separate query mocks for each Article lookup
        self.mock_article_lock_query = MagicMock()
        self.mock_orphan_query = MagicMock()
        self.mock_article_delete_query = MagicMock()

        # Simulate locking the associated articles
        self.mock_article_lock_query.order_by.return_value \
            .select_for_update.return_value \
            .values_list.return_value = article_ids

        # Simulate identifying articles without remaining references
        self.mock_orphan_query.values_list.return_value = orphaned_ids

        # Return the appropriate query for each Article filter call
        self.mock_article.objects.filter.side_effect = [
            self.mock_article_lock_query,
            self.mock_orphan_query,
            self.mock_article_delete_query,
        ]

    def assert_story_deleted(self):

        # Verify the story was retrieved with a row lock requested
        self.mock_story.objects.select_for_update.assert_called_once_with()
        self.mock_story.objects.select_for_update.return_value \
            .get.assert_called_once_with(pk=1)

        # Verify both revision pointers were cleared
        self.assertIsNone(self.story.currentrevisionnum)
        self.assertIsNone(self.story.publishedrevisionnum)

        self.story.save.assert_called_once_with(
            update_fields=[
                "currentrevisionnum",
                "publishedrevisionnum",
            ]
        )

        # Verify story-tag relationships were removed
        self.mock_story_tag.objects.filter.assert_called_once_with(
            storyid=self.story
        )
        self.mock_story_tag.objects.filter.return_value \
            .delete.assert_called_once_with()

        # Verify revision-article relationships were removed
        self.mock_revision_article.objects.filter.return_value \
            .delete.assert_called_once_with()

        # Verify all story revisions were removed
        self.mock_revision.objects.filter.assert_called_once_with(
            storyid=self.story
        )
        self.mock_revision.objects.filter.return_value \
            .delete.assert_called_once_with()

        # Verify the story itself was deleted
        self.story.delete.assert_called_once_with()

    def test_delete_story_without_articles(self):

        # Simulate a story with no associated articles
        article_ids = []
        orphaned_ids = []

        self.configure_article_queries(article_ids, orphaned_ids)

        result = delete_story.__wrapped__(1)

        self.assert_story_deleted()
        self.assert_article_cleanup(article_ids, orphaned_ids)

        # No articles should be reported as deleted
        self.assertEqual(result, 0)

    def assert_article_cleanup(self, article_ids, orphaned_ids):

        # Verify articles were collected from all story revisions
        self.mock_revision_article.objects.filter.return_value \
            .values_list.assert_called_once_with(
                "articleid_id", flat=True
            )

        self.mock_revision_article.objects.filter.return_value \
            .values_list.return_value.distinct.assert_called_once_with()

        # Verify the associated articles were locked in PK order
        self.mock_article_lock_query.order_by.assert_called_once_with("pk")

        self.mock_article_lock_query.order_by.return_value \
            .select_for_update.assert_called_once_with()

        self.mock_article_lock_query.order_by.return_value \
            .select_for_update.return_value \
            .values_list.assert_called_once_with("pk", flat=True)

        # Verify all three Article queries used the correct filters

        self.assertEqual(
            self.mock_article.objects.filter.call_args_list,
            [
                call(pk__in=article_ids),
                call(
                    pk__in=article_ids,
                    revision_links__isnull=True,
                ),
                call(pk__in=orphaned_ids),
            ]
        )

        # Verify orphaned article IDs were retrieved
        self.mock_orphan_query.values_list.assert_called_once_with(
            "pk", flat=True
        )

        # Verify only orphaned article-author relationships were removed
        self.mock_article_author.objects.filter.assert_called_once_with(
            articleid_id__in=orphaned_ids
        )

        self.mock_article_author.objects.filter.return_value \
            .delete.assert_called_once_with()

        # Verify only orphaned article-tag relationships were removed
        self.mock_article_tag.objects.filter.assert_called_once_with(
            articleid_id__in=orphaned_ids
        )

        self.mock_article_tag.objects.filter.return_value \
            .delete.assert_called_once_with()

        # Verify the orphaned article deletion was requested
        self.mock_article_delete_query.delete.assert_called_once_with()

    def test_delete_story_with_all_orphaned_articles(self):

        # Neither article is referenced by another story
        article_ids = [10, 20]
        orphaned_ids = [10, 20]

        self.configure_article_queries(article_ids, orphaned_ids)

        result = delete_story.__wrapped__(1)

        self.assert_story_deleted()
        self.assert_article_cleanup(article_ids, orphaned_ids)

        # Both articles should be reported as deleted
        self.assertEqual(result, 2)

    def test_delete_story_with_all_shared_articles(self):

        # Both articles are still referenced by other stories
        article_ids = [10, 20]
        orphaned_ids = []

        self.configure_article_queries(article_ids, orphaned_ids)

        result = delete_story.__wrapped__(1)

        self.assert_story_deleted()
        self.assert_article_cleanup(article_ids, orphaned_ids)

        # No articles should be reported as deleted
        self.assertEqual(result, 0)

    def test_delete_story_with_mixed_articles(self):

        # Article 20 is shared with another story
        # Articles 10 and 30 are no longer referenced
        article_ids = [10, 20, 30]
        orphaned_ids = [10, 30]

        self.configure_article_queries(article_ids, orphaned_ids)

        result = delete_story.__wrapped__(1)

        self.assert_story_deleted()
        self.assert_article_cleanup(article_ids, orphaned_ids)

        # Only the two orphaned articles should be reported as deleted
        self.assertEqual(result, 2)

    def test_deletion_operation_order(self):

        # Simulate one orphaned article and one shared article
        self.configure_article_queries(
            article_ids=[10, 20],
            orphaned_ids=[10]
        )

        # Create a parent mock to track calls across different mocks
        operations = MagicMock()

        # Register each important operation with the parent mock
        operations.attach_mock(
            self.mock_story.objects.select_for_update,
            "lock_story"
        )

        operations.attach_mock(
            self.mock_revision_article.objects.filter.return_value
                .values_list.return_value.distinct,
            "collect_articles"
        )

        operations.attach_mock(
            self.mock_article_lock_query.order_by.return_value
                .select_for_update,
            "lock_articles"
        )

        operations.attach_mock(
            self.story.save,
            "save_story"
        )

        operations.attach_mock(
            self.mock_story_tag.objects.filter.return_value.delete,
            "delete_story_tags"
        )

        operations.attach_mock(
            self.mock_revision_article.objects.filter.return_value.delete,
            "delete_revision_articles"
        )

        operations.attach_mock(
            self.mock_revision.objects.filter.return_value.delete,
            "delete_revisions"
        )

        operations.attach_mock(
            self.story.delete,
            "delete_story"
        )

        operations.attach_mock(
            self.mock_orphan_query.values_list,
            "find_orphaned_articles"
        )

        operations.attach_mock(
            self.mock_article_author.objects.filter.return_value.delete,
            "delete_article_authors"
        )

        operations.attach_mock(
            self.mock_article_tag.objects.filter.return_value.delete,
            "delete_article_tags"
        )

        operations.attach_mock(
            self.mock_article_delete_query.delete,
            "delete_articles"
        )

        # Execute the deletion service
        result = delete_story.__wrapped__(1)

        # Extract the registered operation names in execution order
        operation_names = [
            recorded_call[0]
            for recorded_call in operations.mock_calls
            if "." not in recorded_call[0]
        ]

        # Verify operations occurred in the expected order
        self.assertEqual(
            operation_names,
            [
                "lock_story",
                "collect_articles",
                "lock_articles",
                "save_story",
                "delete_story_tags",
                "delete_revision_articles",
                "delete_revisions",
                "delete_story",
                "find_orphaned_articles",
                "delete_article_authors",
                "delete_article_tags",
                "delete_articles",
            ]
        )

        self.assertEqual(result, 1)


class StoryDeletionCascadeTests(SimpleTestCase):

    section_name = "Cascading Deletion Configuration"

    def test_article_text_cascades_on_article_deletion(self):

        # Retrieve the relationship between ArticleText and Article
        field = ArticleText._meta.get_field("articleid")

        # Verify article text is configured for cascading deletion
        self.assertIs(
            field.remote_field.on_delete,
            models.CASCADE
        )

    def test_bookmarks_cascade_on_story_deletion(self):

        # Retrieve the relationship between Bookmark and Story
        field = Bookmark._meta.get_field("storyid")

        # Verify bookmarks are configured for cascading deletion
        self.assertIs(
            field.remote_field.on_delete,
            models.CASCADE
        )