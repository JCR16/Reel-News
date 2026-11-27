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


class StoryGenerationTests(SimpleTestCase):
    """Initial Story Generation"""

    def setUp(self):
        # Simulate two source articles supplied by an administrator.
        self.articles = [
            {
                "title": "First Article",
                "link": "https://example.com/first",
                "text": "First article content.",
                "publisher_id": 1,
            },
            {
                "title": "Second Article",
                "link": "https://example.com/second",
                "text": "Second article content.",
                "publisher_id": 2,
            },
        ]

        # Simulate Gemini's generated response.
        self.generated = {
            "headline": "Generated headline",
            "summary": "Generated neutral summary.",
        }

        # Create the mock story and initial revision.
        self.story = MagicMock(spec=Story)
        self.story.pk = 1
        self.story.status = "Draft"

        self.revision = MagicMock(spec=StoryRevision)
        self.revision.revisionnum = 1
        self.revision.status = "Draft"

        # Mock the transaction context manager.
        atomic_patcher = patch(
            "stories.services.story_manager.transaction.atomic"
        )
        self.mock_atomic = atomic_patcher.start()
        self.addCleanup(atomic_patcher.stop)

        # Mock Gemini generation.
        generate_patcher = patch(
            "stories.services.story_manager.generate_story"
        )
        self.mock_generate = generate_patcher.start()
        self.addCleanup(generate_patcher.stop)

        # Mock story creation.
        story_patcher = patch(
            "stories.services.story_manager.create_story"
        )
        self.mock_create_story = story_patcher.start()
        self.addCleanup(story_patcher.stop)

        # Mock revision creation.
        revision_patcher = patch(
            "stories.services.story_manager.create_story_revision"
        )
        self.mock_create_revision = revision_patcher.start()
        self.addCleanup(revision_patcher.stop)

        # Mock article linking.
        link_patcher = patch(
            "stories.services.story_manager.link_revision_article"
        )
        self.mock_link_article = link_patcher.start()
        self.addCleanup(link_patcher.stop)

        # Configure successful default responses.
        self.mock_generate.return_value = self.generated
        self.mock_create_story.return_value = self.story
        self.mock_create_revision.return_value = self.revision

    def test_generate_story(self):
        """Generate and save a new story"""

        result = generate_and_save_story(self.articles)

        # Verify that Gemini received only the source article texts.
        self.mock_generate.assert_called_once_with(
            [
                "First article content.",
                "Second article content.",
            ]
        )

        # Verify that a transaction was opened.
        self.mock_atomic.assert_called_once_with()

        # Verify that a new story was created.
        self.mock_create_story.assert_called_once_with()

        # Verify that Gemini's output was used for the initial revision.
        self.mock_create_revision.assert_called_once_with(
            self.story,
            headline="Generated headline",
            summary="Generated neutral summary.",
        )

        # Verify that both articles were linked to the initial revision.
        self.assertEqual(
            self.mock_link_article.call_args_list,
            [
                call(self.story, self.revision, self.articles[0]),
                call(self.story, self.revision, self.articles[1]),
            ],
        )

        # Verify that the newly created story was returned.
        self.assertIs(result, self.story)

    def test_gemini_generation_failure(self):
        """Prevent database operations when Gemini generation fails"""

        # Simulate a failed Gemini request.
        self.mock_generate.side_effect = RuntimeError(
            "Gemini generation failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Gemini generation failed.",
        ):
            generate_and_save_story(self.articles)

        # Gemini should fail before any transaction is opened.
        self.mock_generate.assert_called_once()
        self.mock_atomic.assert_not_called()

        # Verify that no database operations were attempted.
        self.mock_create_story.assert_not_called()
        self.mock_create_revision.assert_not_called()
        self.mock_link_article.assert_not_called()

    def test_story_creation_failure(self):
        """Stop generation when story creation fails"""

        # Simulate a database error during story creation.
        self.mock_create_story.side_effect = RuntimeError(
            "Story creation failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Story creation failed.",
        ):
            generate_and_save_story(self.articles)

        # Gemini should have completed before the failure.
        self.mock_generate.assert_called_once()
        self.mock_atomic.assert_called_once_with()
        self.mock_create_story.assert_called_once_with()

        # Verify that no dependent records were created.
        self.mock_create_revision.assert_not_called()
        self.mock_link_article.assert_not_called()

    def test_revision_creation_failure(self):
        """Stop generation when initial revision creation fails"""

        # Simulate a database error during revision creation.
        self.mock_create_revision.side_effect = RuntimeError(
            "Revision creation failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Revision creation failed.",
        ):
            generate_and_save_story(self.articles)

        # Verify that generation and story creation were attempted.
        self.mock_generate.assert_called_once()
        self.mock_atomic.assert_called_once_with()
        self.mock_create_story.assert_called_once_with()

        self.mock_create_revision.assert_called_once_with(
            self.story,
            headline="Generated headline",
            summary="Generated neutral summary.",
        )

        # No articles should be linked without a successful revision.
        self.mock_link_article.assert_not_called()

    def test_article_linking_failure(self):
        """Stop generation when article linking fails"""

        # Simulate a failure while linking the first source article.
        self.mock_link_article.side_effect = RuntimeError(
            "Article linking failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Article linking failed.",
        ):
            generate_and_save_story(self.articles)

        # Verify that the story and revision were created first.
        self.mock_create_story.assert_called_once_with()
        self.mock_create_revision.assert_called_once()

        # Verify that linking stopped after the first failure.
        self.mock_link_article.assert_called_once_with(
            self.story,
            self.revision,
            self.articles[0],
        )

    def test_generation_operation_order(self):
        """Initial story generation operation order"""

        # Track calls across all mocked components.
        operations = MagicMock()

        operations.attach_mock(
            self.mock_generate,
            "generate",
        )
        operations.attach_mock(
            self.mock_atomic,
            "atomic",
        )
        operations.attach_mock(
            self.mock_create_story,
            "create_story",
        )
        operations.attach_mock(
            self.mock_create_revision,
            "create_revision",
        )
        operations.attach_mock(
            self.mock_link_article,
            "link_article",
        )

        generate_and_save_story(self.articles)

        # Verify that Gemini executes before the transaction opens
        # and all database operations occur inside the transaction.
        self.assertEqual(
            operations.mock_calls,
            [
                call.generate(
                    [
                        "First article content.",
                        "Second article content.",
                    ]
                ),
                call.atomic(),
                call.atomic().__enter__(),
                call.create_story(),
                call.create_revision(
                    self.story,
                    headline="Generated headline",
                    summary="Generated neutral summary.",
                ),
                call.link_article(
                    self.story,
                    self.revision,
                    self.articles[0],
                ),
                call.link_article(
                    self.story,
                    self.revision,
                    self.articles[1],
                ),
                call.atomic().__exit__(None, None, None),
            ],
        )


class RevisionGenerationTests(SimpleTestCase):
    """Story Revision Generation"""

    def start_patch(self, target):
        # Start a patch and automatically remove it after the test.
        patcher = patch(f"stories.services.story_manager.{target}")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        # Simulate the updated source articles.
        self.articles = [
            {
                "title": "Updated Article",
                "link": "https://example.com/updated",
                "text": "Updated article content.",
                "publisher_id": 1,
            },
            {
                "title": "Additional Article",
                "link": "https://example.com/additional",
                "text": "Additional article content.",
                "publisher_id": 2,
            },
        ]

        # Simulate Gemini's response.
        self.generated = {
            "headline": "Updated headline",
            "summary": "Updated neutral summary.",
        }

        # Create the story as it exists before Gemini generation.
        self.story = MagicMock(spec=Story)
        self.story.pk = 1
        self.story.status = "Draft"
        self.story.currentrevisionnum = 1
        self.story.publishedrevisionnum = None

        # Create a separate mock representing the story retrieved
        # after Gemini generation and database locking.
        self.locked_story = MagicMock(spec=Story)
        self.locked_story.pk = 1
        self.locked_story.status = "Draft"
        self.locked_story.currentrevisionnum = 1
        self.locked_story.publishedrevisionnum = None

        # Create the previous revision.
        self.previous_revision = MagicMock(spec=StoryRevision)
        self.previous_revision.revisionnum = 1
        self.previous_revision.headline = "Original headline"
        self.previous_revision.summary = "Original summary."
        self.previous_revision.status = "Draft"

        # Create the new revision.
        self.new_revision = MagicMock(spec=StoryRevision)
        self.new_revision.revisionnum = 2
        self.new_revision.status = "Draft"

        # Mock database models, services, and transaction operations.
        self.mock_story = self.start_patch("Story")
        self.mock_revision = self.start_patch("StoryRevision")
        self.mock_revision_article = self.start_patch("RevisionArticle")

        self.mock_generate = self.start_patch("generate_story")
        self.mock_create_revision = self.start_patch(
            "create_story_revision"
        )
        self.mock_link_article = self.start_patch(
            "link_revision_article"
        )
        self.mock_cleanup = self.start_patch(
            "cleanup_unused_article_text"
        )

        self.mock_atomic = self.start_patch("transaction.atomic")
        self.mock_on_commit = self.start_patch("transaction.on_commit")

        # Configure successful default database responses.
        self.mock_story.objects.get.return_value = self.story

        self.mock_story.objects.select_for_update.return_value.get.return_value = (
            self.locked_story
        )

        self.mock_revision.objects.get.return_value = (
            self.previous_revision
        )

        # Simulate the previous revision's associated article IDs.
        self.mock_revision_article.objects.filter.return_value.values_list.return_value = [
            10, 20
        ]

        self.mock_generate.return_value = self.generated
        self.mock_create_revision.return_value = self.new_revision

    def assert_no_revision_writes(self):
        # Shared assertions for unsuccessful generation attempts.
        self.mock_create_revision.assert_not_called()
        self.mock_link_article.assert_not_called()
        self.mock_on_commit.assert_not_called()
        self.mock_cleanup.assert_not_called()
        self.story.save.assert_not_called()
        self.locked_story.save.assert_not_called()

    def test_generate_revision(self):
        """Generate a new revision of an existing story"""

        result = generate_and_save_revision(1, self.articles)

        # Verify that the existing story and revision were retrieved.
        self.mock_story.objects.get.assert_called_once_with(
            storyid=1
        )

        self.mock_revision.objects.get.assert_called_once_with(
            storyid_id=1,
            revisionnum=1,
        )

        # Verify that Gemini received the new article texts
        # and the previous revision's content.
        self.mock_generate.assert_called_once_with(
            [
                "Updated article content.",
                "Additional article content.",
            ],
            previous_headline="Original headline",
            previous_summary="Original summary.",
        )

        # Verify that a transaction was opened and the story locked.
        self.mock_atomic.assert_called_once_with()

        self.mock_story.objects.select_for_update.assert_called_once_with()

        self.mock_story.objects.select_for_update.return_value.get.assert_called_once_with(
            storyid=1
        )

        # Verify that the previous revision's article IDs were retrieved.
        self.mock_revision_article.objects.filter.assert_called_once_with(
            storyid=self.locked_story,
            revisionnum=1,
        )

        self.mock_revision_article.objects.filter.return_value.values_list.assert_called_once_with(
            "articleid_id",
            flat=True,
        )

        # Verify that Gemini's output was saved using the locked story.
        self.mock_create_revision.assert_called_once_with(
            self.locked_story,
            headline="Updated headline",
            summary="Updated neutral summary.",
        )

        # Verify that both updated source articles were linked.
        self.assertEqual(
            self.mock_link_article.call_args_list,
            [
                call(
                    self.locked_story,
                    self.new_revision,
                    self.articles[0],
                ),
                call(
                    self.locked_story,
                    self.new_revision,
                    self.articles[1],
                ),
            ],
        )

        # Cleanup should be scheduled rather than executed immediately.
        self.mock_on_commit.assert_called_once()
        self.mock_cleanup.assert_not_called()

        self.assertIs(result, self.new_revision)

    def test_generate_revision_preserve_publication(self):
        """Preserve existing publication during revision generation"""

        # Simulate a story whose first revision is published.
        self.story.status = "Published"
        self.story.publishedrevisionnum = 1

        self.locked_story.status = "Published"
        self.locked_story.publishedrevisionnum = 1

        self.previous_revision.status = "Published"

        result = generate_and_save_revision(1, self.articles)

        # Verify that the orchestration function does not modify
        # the existing publication status or published pointer.
        self.assertEqual(self.locked_story.status, "Published")
        self.assertEqual(self.locked_story.publishedrevisionnum, 1)

        self.assertEqual(self.previous_revision.status, "Published")
        self.previous_revision.save.assert_not_called()

        self.locked_story.save.assert_not_called()

        self.mock_create_revision.assert_called_once_with(
            self.locked_story,
            headline="Updated headline",
            summary="Updated neutral summary.",
        )

        self.assertIs(result, self.new_revision)

    def test_generate_revision_nonexistent_story(self):
        """Handle revision generation for a nonexistent story"""

        self.mock_story.objects.get.side_effect = Story.DoesNotExist

        with self.assertRaises(Story.DoesNotExist):
            generate_and_save_revision(999, self.articles)

        self.mock_story.objects.get.assert_called_once_with(
            storyid=999
        )

        # Generation should stop before retrieving a revision.
        self.mock_revision.objects.get.assert_not_called()
        self.mock_generate.assert_not_called()
        self.mock_atomic.assert_not_called()

        self.assert_no_revision_writes()

    def test_generate_revision_archived_story(self):
        """Prevent revision generation for an archived story"""

        self.story.status = "Archived"
        self.story.publishedrevisionnum = 1

        with self.assertRaisesMessage(
            ValueError,
            "Archived stories must be restored before generating revisions.",
        ):
            generate_and_save_revision(1, self.articles)

        # Archived stories should be rejected before calling Gemini.
        self.mock_revision.objects.get.assert_not_called()
        self.mock_generate.assert_not_called()
        self.mock_atomic.assert_not_called()

        self.assert_no_revision_writes()

    def test_generate_revision_missing_previous_revision(self):
        """Prevent generation when the previous revision is missing"""

        self.mock_revision.objects.get.side_effect = (
            StoryRevision.DoesNotExist
        )

        with self.assertRaises(StoryRevision.DoesNotExist):
            generate_and_save_revision(1, self.articles)

        self.mock_revision.objects.get.assert_called_once_with(
            storyid_id=1,
            revisionnum=1,
        )

        # Gemini cannot generate an update without the previous revision.
        self.mock_generate.assert_not_called()
        self.mock_atomic.assert_not_called()

        self.assert_no_revision_writes()

    def test_revision_gemini_failure(self):
        """Prevent revision writes when Gemini generation fails"""

        self.mock_generate.side_effect = RuntimeError(
            "Gemini generation failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Gemini generation failed.",
        ):
            generate_and_save_revision(1, self.articles)

        self.mock_generate.assert_called_once()

        # No transaction or story lock should be requested.
        self.mock_atomic.assert_not_called()
        self.mock_story.objects.select_for_update.assert_not_called()

        self.assert_no_revision_writes()

    def test_story_archived_during_generation(self):
        """Prevent revision creation when a story is archived during generation"""

        # The initial story is eligible, but its locked state is archived.
        self.story.status = "Published"
        self.story.publishedrevisionnum = 1

        self.locked_story.status = "Archived"
        self.locked_story.publishedrevisionnum = 1

        with self.assertRaisesMessage(
            ValueError,
            "The story was archived during revision generation.",
        ):
            generate_and_save_revision(1, self.articles)

        # Gemini completed before the archived status was discovered.
        self.mock_generate.assert_called_once()
        self.mock_atomic.assert_called_once_with()
        self.mock_story.objects.select_for_update.assert_called_once_with()

        # No new revision should be created.
        self.mock_revision_article.objects.filter.assert_not_called()
        self.assert_no_revision_writes()

    def test_current_revision_changed_during_generation(self):
        """Prevent revision creation when the current revision changes"""

        # Simulate another administrator creating a revision
        # while Gemini is generating content.
        self.locked_story.currentrevisionnum = 2

        with self.assertRaisesMessage(
            ValueError,
            "The current revision changed during generation.",
        ):
            generate_and_save_revision(1, self.articles)

        self.mock_generate.assert_called_once()
        self.mock_atomic.assert_called_once_with()
        self.mock_story.objects.select_for_update.assert_called_once_with()

        # The newer revision must not be overwritten.
        self.assertEqual(self.locked_story.currentrevisionnum, 2)

        self.mock_revision_article.objects.filter.assert_not_called()
        self.assert_no_revision_writes()

    def test_generated_revision_creation_failure(self):
        """Stop generation when the new revision cannot be created"""

        self.mock_create_revision.side_effect = RuntimeError(
            "Revision creation failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Revision creation failed.",
        ):
            generate_and_save_revision(1, self.articles)

        self.mock_create_revision.assert_called_once()

        # No articles should be linked to a failed revision.
        self.mock_link_article.assert_not_called()
        self.mock_on_commit.assert_not_called()
        self.mock_cleanup.assert_not_called()

    def test_generated_revision_article_linking_failure(self):
        """Stop revision generation when article linking fails"""

        self.mock_link_article.side_effect = RuntimeError(
            "Article linking failed."
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Article linking failed.",
        ):
            generate_and_save_revision(1, self.articles)

        self.mock_create_revision.assert_called_once()

        # Linking should stop after the first failure.
        self.mock_link_article.assert_called_once_with(
            self.locked_story,
            self.new_revision,
            self.articles[0],
        )

        # Cleanup must not be scheduled after a failed operation.
        self.mock_on_commit.assert_not_called()
        self.mock_cleanup.assert_not_called()

    def test_revision_cleanup_callback(self):
        """Schedule cleanup using the previous revision's article IDs"""

        generate_and_save_revision(1, self.articles)

        self.mock_on_commit.assert_called_once()

        # Retrieve the callback passed to transaction.on_commit().
        callback = self.mock_on_commit.call_args.args[0]

        # Cleanup should not have executed yet.
        self.mock_cleanup.assert_not_called()

        # Manually execute the callback to simulate a successful commit.
        callback()

        # Only the previous revision's articles should be examined.
        self.mock_cleanup.assert_called_once_with([10, 20])

    def test_revision_generation_operation_order(self):
        """Story revision generation operation order"""

        # Track calls across the individual mocked components.
        operations = MagicMock()

        operations.attach_mock(
            self.mock_story.objects.get,
            "get_story",
        )
        operations.attach_mock(
            self.mock_revision.objects.get,
            "get_revision",
        )
        operations.attach_mock(
            self.mock_generate,
            "generate",
        )
        operations.attach_mock(
            self.mock_atomic,
            "atomic",
        )
        operations.attach_mock(
            self.mock_story.objects.select_for_update,
            "lock_story",
        )
        operations.attach_mock(
            self.mock_revision_article.objects.filter,
            "get_articles",
        )
        operations.attach_mock(
            self.mock_create_revision,
            "create_revision",
        )
        operations.attach_mock(
            self.mock_link_article,
            "link_article",
        )
        operations.attach_mock(
            self.mock_on_commit,
            "on_commit",
        )

        generate_and_save_revision(1, self.articles)

        # Retrieve the scheduled callback for the expected call sequence.
        callback = self.mock_on_commit.call_args.args[0]

        # Verify the complete operation sequence.
        self.assertEqual(
            operations.mock_calls,
            [
                call.get_story(storyid=1),
                call.get_revision(
                    storyid_id=1,
                    revisionnum=1,
                ),
                call.generate(
                    [
                        "Updated article content.",
                        "Additional article content.",
                    ],
                    previous_headline="Original headline",
                    previous_summary="Original summary.",
                ),
                call.atomic(),
                call.atomic().__enter__(),
                call.lock_story(),
                call.lock_story().get(storyid=1),
                call.get_articles(
                    storyid=self.locked_story,
                    revisionnum=1,
                ),
                call.get_articles().values_list(
                    "articleid_id",
                    flat=True,
                ),
                call.create_revision(
                    self.locked_story,
                    headline="Updated headline",
                    summary="Updated neutral summary.",
                ),
                call.link_article(
                    self.locked_story,
                    self.new_revision,
                    self.articles[0],
                ),
                call.link_article(
                    self.locked_story,
                    self.new_revision,
                    self.articles[1],
                ),
                call.on_commit(callback),
                call.atomic().__exit__(None, None, None),
            ],
        )