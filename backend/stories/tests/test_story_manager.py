from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from django.test import SimpleTestCase

from stories.models import (
    Story,
    StoryRevision,
    Article,
    ArticleText,
    Publisher,
    RevisionArticle,
)

from stories.services.story_manager import (
    create_story,
    create_story_revision,
    link_revision_article,
    generate_and_save_story,
    generate_and_save_revision,
    regenerate_rejected_revision,
)


class StoryCreationTests(SimpleTestCase):
    """Story and Revision Creation"""

    def setUp(self):
        # Use a fixed timestamp for predictable assertions.
        self.now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)

        # Create a mock story without any revisions.
        self.story = MagicMock(spec=Story)
        self.story.pk = 1
        self.story.status = "Draft"
        self.story.currentrevisionnum = None
        self.story.publishedrevisionnum = None
        self.story.datemodified = None

        # Create a mock revision.
        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 1
        self.revision.status = "Draft"

    @patch("stories.services.story_manager.timezone.now")
    @patch("stories.services.story_manager.Story")
    def test_create_story(self, mock_story, mock_now):
        """Create a new Draft story"""

        # Simulate the current time and database creation.
        mock_now.return_value = self.now
        mock_story.objects.create.return_value = self.story

        # Create the story without opening a database transaction.
        result = create_story.__wrapped__()

        # Verify that the story was created with the correct values.
        mock_story.objects.create.assert_called_once_with(
            currentrevisionnum=None,
            datecreated=self.now,
            datemodified=self.now,
            status="Draft",
        )

        # Verify that the saved story was returned.
        self.assertIs(result, self.story)

    @patch("stories.services.story_manager.timezone.now")
    @patch("stories.services.story_manager.StoryRevision")
    def test_create_first_revision(self, mock_revision, mock_now):
        """Create the first revision of a story"""

        mock_now.return_value = self.now
        mock_revision.objects.create.return_value = self.revision

        # Create the first revision.
        result = create_story_revision.__wrapped__(
            self.story,
            headline="Initial headline",
            summary="Initial summary.",
        )

        # Verify that revision numbering starts at 1.
        mock_revision.objects.create.assert_called_once_with(
            storyid=self.story,
            revisionnum=1,
            datecreated=self.now,
            headline="Initial headline",
            summary="Initial summary.",
        )

        # Verify that the story now references its first revision.
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertEqual(self.story.datemodified, self.now)
        self.assertEqual(self.story.status, "Draft")
        self.assertIsNone(self.story.publishedrevisionnum)

        self.story.save.assert_called_once_with(
            update_fields=["currentrevisionnum", "datemodified"]
        )

        self.assertIs(result, self.revision)

    @patch("stories.services.story_manager.timezone.now")
    @patch("stories.services.story_manager.StoryRevision")
    def test_increment_revision_number(self, mock_revision, mock_now):
        """Increment an existing revision number"""

        # Test several existing revision numbers.
        for current_number in [1, 5, 10]:
            with self.subTest(current_revision=current_number):

                # Reset mocks between scenarios.
                self.setUp()
                mock_revision.reset_mock()
                mock_now.reset_mock()

                self.story.currentrevisionnum = current_number
                self.revision.revisionnum = current_number + 1

                mock_now.return_value = self.now
                mock_revision.objects.create.return_value = self.revision

                result = create_story_revision.__wrapped__(
                    self.story,
                    headline="Updated headline",
                    summary="Updated summary.",
                )

                # Verify that the revision number increased by one.
                mock_revision.objects.create.assert_called_once_with(
                    storyid=self.story,
                    revisionnum=current_number + 1,
                    datecreated=self.now,
                    headline="Updated headline",
                    summary="Updated summary.",
                )

                self.assertEqual(
                    self.story.currentrevisionnum,
                    current_number + 1,
                )
                self.assertEqual(self.story.datemodified, self.now)
                self.assertEqual(self.story.status, "Draft")
                self.assertIsNone(self.story.publishedrevisionnum)

                self.story.save.assert_called_once_with(
                    update_fields=["currentrevisionnum", "datemodified"]
                )

                self.assertIs(result, self.revision)

    @patch("stories.services.story_manager.timezone.now")
    @patch("stories.services.story_manager.StoryRevision")
    def test_preserve_published_revision(self, mock_revision, mock_now):
        """Preserve the published revision when creating a new revision"""

        # Simulate a story with an existing published revision.
        self.story.status = "Published"
        self.story.currentrevisionnum = 2
        self.story.publishedrevisionnum = 1
        self.revision.revisionnum = 3

        mock_now.return_value = self.now
        mock_revision.objects.create.return_value = self.revision

        result = create_story_revision.__wrapped__(
            self.story,
            headline="New headline",
            summary="New summary.",
        )

        # Verify that the new revision was created.
        mock_revision.objects.create.assert_called_once_with(
            storyid=self.story,
            revisionnum=3,
            datecreated=self.now,
            headline="New headline",
            summary="New summary.",
        )

        # Only the current revision pointer should advance.
        self.assertEqual(self.story.currentrevisionnum, 3)
        self.assertEqual(self.story.publishedrevisionnum, 1)
        self.assertEqual(self.story.status, "Published")
        self.assertEqual(self.story.datemodified, self.now)

        self.story.save.assert_called_once_with(
            update_fields=["currentrevisionnum", "datemodified"]
        )

        self.assertIs(result, self.revision)

    @patch("stories.services.story_manager.timezone.now")
    @patch("stories.services.story_manager.StoryRevision")
    def test_revision_creation_failure(self, mock_revision, mock_now):
        """Preserve story state when revision creation fails"""

        self.story.currentrevisionnum = 1
        mock_now.return_value = self.now

        # Simulate an exception during revision creation.
        mock_revision.objects.create.side_effect = RuntimeError(
            "Revision creation failed."
        )

        # Verify that the exception is propagated.
        with self.assertRaisesMessage(
            RuntimeError,
            "Revision creation failed.",
        ):
            create_story_revision.__wrapped__(
                self.story,
                headline="New headline",
                summary="New summary.",
            )

        # Verify that the story was not updated.
        self.assertEqual(self.story.currentrevisionnum, 1)
        self.assertEqual(self.story.status, "Draft")
        self.assertIsNone(self.story.publishedrevisionnum)
        self.assertIsNone(self.story.datemodified)

        self.story.save.assert_not_called()


class ArticleLinkingTests(SimpleTestCase):
    """Revision Article Linking"""

    def setUp(self):
        # Create the mock story and revision.
        self.story = MagicMock(spec=Story)
        self.story.pk = 1

        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 2

        # Create the mock publisher and article.
        self.publisher = MagicMock(spec=Publisher)
        self.publisher.pk = 5

        self.article = MagicMock(spec=Article)
        self.article.pk = 10

        # Create the mock article text and revision relationship.
        self.article_text = MagicMock(spec=ArticleText)
        self.revision_link = MagicMock(spec=RevisionArticle)

        # Simulate the source article data supplied to the service.
        self.article_data = {
            "title": "Example Article",
            "link": "https://example.com/article",
            "text": "This is the original article text.",
            "publisher_id": 5,
        }

    @patch("stories.services.story_manager.RevisionArticle")
    @patch("stories.services.story_manager.ArticleText")
    @patch("stories.services.story_manager.Article")
    @patch("stories.services.story_manager.get_or_create_article")
    @patch("stories.services.story_manager.Publisher")
    def test_link_article(
        self,
        mock_publisher,
        mock_get_article,
        mock_article,
        mock_article_text,
        mock_revision_article,
    ):
        """Link an article to a story revision"""

        # Simulate publisher and article retrieval.
        mock_publisher.objects.get.return_value = self.publisher
        mock_get_article.return_value = self.article

        # Simulate retrieving the locked article.
        mock_article.objects.select_for_update.return_value.get.return_value = (
            self.article
        )

        # Simulate storing the article text.
        mock_article_text.objects.update_or_create.return_value = (
            self.article_text,
            True,
        )

        # Simulate creating the revision relationship.
        mock_revision_article.objects.get_or_create.return_value = (
            self.revision_link,
            True,
        )

        result = link_revision_article(
            self.story,
            self.revision,
            self.article_data,
        )

        # Verify that the correct publisher was retrieved.
        mock_publisher.objects.get.assert_called_once_with(
            publisherid=5
        )

        # Verify that the correct article data was supplied.
        mock_get_article.assert_called_once_with(
            title="Example Article",
            link="https://example.com/article",
            text="This is the original article text.",
            publisher=self.publisher,
        )

        # Verify that the article was locked.
        mock_article.objects.select_for_update.assert_called_once_with()
        mock_article.objects.select_for_update.return_value.get.assert_called_once_with(
            pk=10
        )

        # Verify that the original source text was retained.
        mock_article_text.objects.update_or_create.assert_called_once_with(
            articleid=self.article,
            defaults={"text": "This is the original article text."},
        )

        # Verify that the article was linked to the correct revision.
        mock_revision_article.objects.get_or_create.assert_called_once_with(
            articleid=self.article,
            storyid=self.story,
            revisionnum=2,
        )

        self.assertIs(result, self.revision_link)

    @patch("stories.services.story_manager.RevisionArticle")
    @patch("stories.services.story_manager.ArticleText")
    @patch("stories.services.story_manager.Article")
    @patch("stories.services.story_manager.get_or_create_article")
    @patch("stories.services.story_manager.Publisher")
    def test_reuse_existing_article_relationship(
        self,
        mock_publisher,
        mock_get_article,
        mock_article,
        mock_article_text,
        mock_revision_article,
    ):
        """Reuse an existing article relationship"""

        mock_publisher.objects.get.return_value = self.publisher
        mock_get_article.return_value = self.article

        mock_article.objects.select_for_update.return_value.get.return_value = (
            self.article
        )

        # Test both restoring missing text and updating existing text.
        for text_created in [True, False]:
            with self.subTest(text_created=text_created):

                mock_article_text.reset_mock()
                mock_revision_article.reset_mock()

                mock_article_text.objects.update_or_create.return_value = (
                    self.article_text,
                    text_created,
                )

                # False indicates that the relationship already exists.
                mock_revision_article.objects.get_or_create.return_value = (
                    self.revision_link,
                    False,
                )

                result = link_revision_article(
                    self.story,
                    self.revision,
                    self.article_data,
                )

                # Verify that source text is stored even when
                # the article relationship already exists.
                mock_article_text.objects.update_or_create.assert_called_once_with(
                    articleid=self.article,
                    defaults={
                        "text": "This is the original article text."
                    },
                )

                mock_revision_article.objects.get_or_create.assert_called_once_with(
                    articleid=self.article,
                    storyid=self.story,
                    revisionnum=2,
                )

                # Verify that the existing relationship was returned.
                self.assertIs(result, self.revision_link)

    @patch("stories.services.story_manager.RevisionArticle")
    @patch("stories.services.story_manager.ArticleText")
    @patch("stories.services.story_manager.Article")
    @patch("stories.services.story_manager.get_or_create_article")
    @patch("stories.services.story_manager.Publisher")
    def test_link_article_missing_publisher(
        self,
        mock_publisher,
        mock_get_article,
        mock_article,
        mock_article_text,
        mock_revision_article,
    ):
        """Prevent article linking when the publisher does not exist"""

        # Simulate the publisher not existing.
        mock_publisher.objects.get.side_effect = Publisher.DoesNotExist

        with self.assertRaises(Publisher.DoesNotExist):
            link_revision_article(
                self.story,
                self.revision,
                self.article_data,
            )

        mock_publisher.objects.get.assert_called_once_with(
            publisherid=5
        )

        # Verify that no article operations were attempted.
        mock_get_article.assert_not_called()
        mock_article.objects.select_for_update.assert_not_called()
        mock_article_text.objects.update_or_create.assert_not_called()
        mock_revision_article.objects.get_or_create.assert_not_called()

    @patch("stories.services.story_manager.RevisionArticle")
    @patch("stories.services.story_manager.ArticleText")
    @patch("stories.services.story_manager.Article")
    @patch("stories.services.story_manager.get_or_create_article")
    @patch("stories.services.story_manager.Publisher")
    def test_article_linking_operation_order(
        self,
        mock_publisher,
        mock_get_article,
        mock_article,
        mock_article_text,
        mock_revision_article,
    ):
        """Article linking operation order"""

        mock_publisher.objects.get.return_value = self.publisher
        mock_get_article.return_value = self.article

        mock_article.objects.select_for_update.return_value.get.return_value = (
            self.article
        )

        mock_article_text.objects.update_or_create.return_value = (
            self.article_text,
            True,
        )

        mock_revision_article.objects.get_or_create.return_value = (
            self.revision_link,
            True,
        )

        # Attach the individual mocks to a shared parent so
        # calls can be tracked across multiple components.
        operations = MagicMock()

        operations.attach_mock(
            mock_publisher.objects.get,
            "get_publisher",
        )
        operations.attach_mock(
            mock_get_article,
            "get_article",
        )
        operations.attach_mock(
            mock_article.objects.select_for_update,
            "lock_article",
        )
        operations.attach_mock(
            mock_article_text.objects.update_or_create,
            "store_text",
        )
        operations.attach_mock(
            mock_revision_article.objects.get_or_create,
            "link_article",
        )

        link_revision_article(
            self.story,
            self.revision,
            self.article_data,
        )

        # Verify that operations occurred in the correct order.
        self.assertEqual(
            operations.mock_calls,
            [
                call.get_publisher(publisherid=5),
                call.get_article(
                    title="Example Article",
                    link="https://example.com/article",
                    text="This is the original article text.",
                    publisher=self.publisher,
                ),
                call.lock_article(),
                call.lock_article().get(pk=10),
                call.store_text(
                    articleid=self.article,
                    defaults={
                        "text": "This is the original article text."
                    },
                ),
                call.link_article(
                    articleid=self.article,
                    storyid=self.story,
                    revisionnum=2,
                ),
            ],
        )