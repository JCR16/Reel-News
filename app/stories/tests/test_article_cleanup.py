from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase
from django.db.models import F, OuterRef

from stories.services.story_manager import (
    find_unused_article_text,
    cleanup_unused_article_text,
)


class FindUnusedArticleTextTests(SimpleTestCase):
    """Unused Article Text Identification"""

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test.
        patcher = patch(f"stories.services.story_manager.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        # Mock the models involved in identifying unused text.
        self.mock_revision = self.start_patch("StoryRevision")
        self.mock_revision_article = self.start_patch("RevisionArticle")
        self.mock_article_text = self.start_patch("ArticleText")

        # Mock Exists so it can accept our mocked queryset.
        self.mock_exists = self.start_patch("Exists")

        # Create mock querysets representing each query stage.
        self.link_queryset = MagicMock()
        self.link_story_ids = MagicMock()
        self.revision_queryset = MagicMock()

        self.all_text = MagicMock()
        self.restricted_text = MagicMock()
        self.annotated_text = MagicMock()
        self.unused_text = MagicMock()

        # Configure the revision article subquery.
        self.mock_revision_article.objects.filter.return_value = (
            self.link_queryset
        )

        self.link_queryset.values.return_value = (
            self.link_story_ids
        )

        # Configure the revision eligibility subquery.
        self.mock_revision.objects.filter.return_value = (
            self.revision_queryset
        )

        # Configure the ArticleText queryset.
        self.mock_article_text.objects.all.return_value = (
            self.all_text
        )

        self.all_text.filter.return_value = self.restricted_text

        # Both unrestricted and restricted queries use
        # the same annotation and final filtering stages.
        self.all_text.annotate.return_value = self.annotated_text
        self.restricted_text.annotate.return_value = (
            self.annotated_text
        )

        self.annotated_text.filter.return_value = self.unused_text

    def test_find_all_unused_article_text(self):
        """Identify unused text across all articles"""

        result = find_unused_article_text()

        # Verify that all stored article text was examined.
        self.mock_article_text.objects.all.assert_called_once_with()

        # No article ID restriction should be applied.
        self.all_text.filter.assert_not_called()

        # Verify that the eligibility annotation was applied.
        self.all_text.annotate.assert_called_once_with(
            is_needed=self.mock_exists.return_value
        )

        # Only text that is not needed should be returned.
        self.annotated_text.filter.assert_called_once_with(
            is_needed=False
        )

        self.assertIs(result, self.unused_text)

        # Identification alone must not delete anything.
        self.unused_text.delete.assert_not_called()

    def test_find_specific_unused_article_text(self):
        """Identify unused text for specific articles"""

        result = find_unused_article_text([10, 20])

        # Verify that examination was restricted to the supplied IDs.
        self.all_text.filter.assert_called_once_with(
            articleid_id__in=[10, 20]
        )

        # Annotation should occur on the restricted queryset.
        self.restricted_text.annotate.assert_called_once_with(
            is_needed=self.mock_exists.return_value
        )

        self.all_text.annotate.assert_not_called()

        self.annotated_text.filter.assert_called_once_with(
            is_needed=False
        )

        self.assertIs(result, self.unused_text)
        self.unused_text.delete.assert_not_called()

    def test_find_unused_text_empty_article_ids(self):
        """Preserve an empty article ID restriction"""

        result = find_unused_article_text([])

        # An empty list must not be treated as an unrestricted query.
        self.all_text.filter.assert_called_once_with(
            articleid_id__in=[]
        )

        self.restricted_text.annotate.assert_called_once_with(
            is_needed=self.mock_exists.return_value
        )

        self.all_text.annotate.assert_not_called()

        self.annotated_text.filter.assert_called_once_with(
            is_needed=False
        )

        self.assertIs(result, self.unused_text)
        self.unused_text.delete.assert_not_called()

    def test_unused_text_eligibility_query(self):
        """Construct the correct article text eligibility query"""

        find_unused_article_text()

        # Verify that the subquery identifies relationships
        # belonging to the current revision of each story.
        self.mock_revision_article.objects.filter.assert_called_once_with(
            articleid_id=OuterRef(OuterRef("articleid_id")),
            revisionnum=F("storyid__currentrevisionnum"),
        )

        self.link_queryset.values.assert_called_once_with(
            "storyid_id"
        )

        # Only current Draft and Rejected revisions require
        # their original source article text.
        self.mock_revision.objects.filter.assert_called_once_with(
            storyid_id__in=self.link_story_ids,
            revisionnum=F("storyid__currentrevisionnum"),
            status__in=["Draft", "Rejected"],
        )

        # Verify that the revision subquery is used to determine
        # whether an article's stored text is still needed.
        self.mock_exists.assert_called_once_with(
            self.revision_queryset
        )

        self.all_text.annotate.assert_called_once_with(
            is_needed=self.mock_exists.return_value
        )

        self.annotated_text.filter.assert_called_once_with(
            is_needed=False
        )


class ArticleTextCleanupTests(SimpleTestCase):
    """Unused Article Text Cleanup"""

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test.
        patcher = patch(f"stories.services.story_manager.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        # Mock the models and eligibility lookup service.
        self.mock_article = self.start_patch("Article")
        self.mock_article_text = self.start_patch("ArticleText")
        self.mock_find_unused = self.start_patch(
            "find_unused_article_text"
        )

        # Create mock querysets for each stage of article locking.
        self.stored_text_ids = MagicMock()
        self.articles = MagicMock()
        self.restricted_articles = MagicMock()
        self.ordered_articles = MagicMock()
        self.locked_articles = MagicMock()

        # Create the queryset representing unused article text.
        self.unused_text = MagicMock()

        # Configure identification of articles with stored text.
        self.mock_article_text.objects.values.return_value = (
            self.stored_text_ids
        )

        self.mock_article.objects.filter.return_value = (
            self.articles
        )

        # Configure optional article ID restrictions.
        self.articles.filter.return_value = (
            self.restricted_articles
        )

        # Both unrestricted and restricted queries proceed
        # through ordering and row locking.
        self.articles.order_by.return_value = (
            self.ordered_articles
        )

        self.restricted_articles.order_by.return_value = (
            self.ordered_articles
        )

        self.ordered_articles.select_for_update.return_value = (
            self.locked_articles
        )

        # Simulate the IDs of the successfully locked articles.
        self.locked_articles.values_list.return_value = [10, 20]

        # Simulate two unused ArticleText records.
        self.mock_find_unused.return_value = self.unused_text
        self.unused_text.count.return_value = 2
        self.unused_text.delete.return_value = (
            2,
            {"stories.ArticleText": 2},
        )

    def test_cleanup_all_unused_article_text(self):
        """Clean up unused text across all articles"""

        result = cleanup_unused_article_text.__wrapped__()

        # Verify that only articles with stored text were selected.
        self.mock_article_text.objects.values.assert_called_once_with(
            "articleid_id"
        )

        self.mock_article.objects.filter.assert_called_once_with(
            pk__in=self.stored_text_ids
        )

        # No additional article ID restriction should be applied.
        self.articles.filter.assert_not_called()

        # Verify that articles were ordered and locked.
        self.articles.order_by.assert_called_once_with("pk")

        self.ordered_articles.select_for_update.assert_called_once_with()

        self.locked_articles.values_list.assert_called_once_with(
            "pk",
            flat=True,
        )

        # Eligibility must be checked using the locked article IDs.
        self.mock_find_unused.assert_called_once_with([10, 20])

        # Verify that unused text was counted and deleted.
        self.unused_text.count.assert_called_once_with()
        self.unused_text.delete.assert_called_once_with()

        # Verify that the number of deleted text records was returned.
        self.assertEqual(result, 2)

        # Article records themselves must not be deleted.
        self.articles.delete.assert_not_called()
        self.locked_articles.delete.assert_not_called()

    def test_cleanup_specific_article_text(self):
        """Restrict cleanup to specific articles"""

        # Simulate only one requested article having stored text.
        self.locked_articles.values_list.return_value = [10]
        self.unused_text.count.return_value = 1

        result = cleanup_unused_article_text.__wrapped__(
            [10, 30]
        )

        # Verify that cleanup was restricted to the requested IDs.
        self.articles.filter.assert_called_once_with(
            pk__in=[10, 30]
        )

        # Verify that only the restricted queryset was ordered.
        self.restricted_articles.order_by.assert_called_once_with(
            "pk"
        )

        self.articles.order_by.assert_not_called()

        self.ordered_articles.select_for_update.assert_called_once_with()

        # Eligibility should be checked only for articles
        # that were actually selected and locked.
        self.mock_find_unused.assert_called_once_with([10])

        self.unused_text.count.assert_called_once_with()
        self.unused_text.delete.assert_called_once_with()

        self.assertEqual(result, 1)

    def test_cleanup_empty_article_ids(self):
        """Preserve an empty cleanup restriction"""

        # Simulate no articles being selected or locked.
        self.locked_articles.values_list.return_value = []
        self.unused_text.count.return_value = 0

        result = cleanup_unused_article_text.__wrapped__([])

        # An empty list must not trigger unrestricted cleanup.
        self.articles.filter.assert_called_once_with(
            pk__in=[]
        )

        self.restricted_articles.order_by.assert_called_once_with(
            "pk"
        )

        self.articles.order_by.assert_not_called()

        self.mock_find_unused.assert_called_once_with([])

        self.unused_text.count.assert_called_once_with()
        self.unused_text.delete.assert_called_once_with()

        self.assertEqual(result, 0)

    def test_cleanup_no_unused_article_text(self):
        """Handle cleanup when no article text is eligible"""

        # Simulate all stored text still being needed.
        self.unused_text.count.return_value = 0
        self.unused_text.delete.return_value = (0, {})

        result = cleanup_unused_article_text.__wrapped__()

        self.mock_find_unused.assert_called_once_with([10, 20])

        # The service still calls delete on the empty queryset.
        self.unused_text.count.assert_called_once_with()
        self.unused_text.delete.assert_called_once_with()

        self.assertEqual(result, 0)

        # No Article records should be deleted.
        self.articles.delete.assert_not_called()
        self.locked_articles.delete.assert_not_called()

    def test_cleanup_eligibility_lookup_failure(self):
        """Prevent deletion when eligibility lookup fails"""

        # Simulate a failure while identifying unused text.
        self.mock_find_unused.side_effect = RuntimeError(
            "Eligibility lookup failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Eligibility lookup failed.",
        ):
            cleanup_unused_article_text.__wrapped__()

        # Articles should have been locked before the lookup.
        self.ordered_articles.select_for_update.assert_called_once_with()

        self.mock_find_unused.assert_called_once_with([10, 20])

        # No deletion should occur after a failed eligibility check.
        self.unused_text.count.assert_not_called()
        self.unused_text.delete.assert_not_called()

    def test_cleanup_deletion_failure(self):
        """Propagate article text deletion failures"""

        # Simulate a database error during deletion.
        self.unused_text.delete.side_effect = RuntimeError(
            "Article text deletion failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Article text deletion failed.",
        ):
            cleanup_unused_article_text.__wrapped__()

        # Verify that eligibility was checked before deletion.
        self.mock_find_unused.assert_called_once_with([10, 20])

        self.unused_text.count.assert_called_once_with()
        self.unused_text.delete.assert_called_once_with()

        # Article records must remain outside the deletion operation.
        self.articles.delete.assert_not_called()
        self.locked_articles.delete.assert_not_called()

    def test_cleanup_operation_order(self):
        """Article text cleanup operation order"""

        # Track calls across all relevant mocked components.
        operations = MagicMock()

        operations.attach_mock(
            self.mock_article_text.objects.values,
            "get_stored_text_ids",
        )

        operations.attach_mock(
            self.mock_article.objects.filter,
            "get_articles",
        )

        operations.attach_mock(
            self.articles.order_by,
            "order_articles",
        )

        operations.attach_mock(
            self.ordered_articles.select_for_update,
            "lock_articles",
        )

        operations.attach_mock(
            self.locked_articles.values_list,
            "get_locked_ids",
        )

        operations.attach_mock(
            self.mock_find_unused,
            "find_unused",
        )

        operations.attach_mock(
            self.unused_text.count,
            "count_unused",
        )

        operations.attach_mock(
            self.unused_text.delete,
            "delete_unused",
        )

        result = cleanup_unused_article_text.__wrapped__()

        # Verify that eligibility is evaluated only after
        # acquiring article locks and before deleting text.
        self.assertEqual(
            operations.mock_calls,
            [
                call.get_stored_text_ids("articleid_id"),
                call.get_articles(pk__in=self.stored_text_ids),
                call.order_articles("pk"),
                call.lock_articles(),
                call.get_locked_ids("pk", flat=True),
                call.find_unused([10, 20]),
                call.count_unused(),
                call.delete_unused(),
            ],
        )

        self.assertEqual(result, 2)