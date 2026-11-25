from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected
from django.contrib.admin import helpers
from .models import Publisher, Article, Story, StoryRevision, RevisionArticle, Tag, StoryTag

from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html_join, format_html
from django.utils.safestring import mark_safe
from django.http import Http404, HttpResponseNotAllowed
from django.core.exceptions import PermissionDenied

from django.db import transaction
from django.db.models import F, Q

from .services.story_archiving import (
    archive_story,
    restore_story,
)
from .services.story_manager import (
    generate_and_save_story,
    generate_and_save_revision,
    regenerate_rejected_revision,
    cleanup_unused_article_text,
)
from .services.story_deletion import (
    delete_story,
    can_delete_story,
)

from .forms import ArticleFormSet, RevisionRejectionForm, StoryAdminForm, TagAdminForm

import logging

logger = logging.getLogger(__name__)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """
    Allows administrators to create, edit, and delete
    tags through Django Admin.
    """
    form = TagAdminForm
    
    # Show tag information in the Admin list.
    list_display = ("tagid", "name", "description")

    # Allow administrators to search tags by name.
    search_fields = ("name",)

    # Sort tags alphabetically.
    ordering = ("name",)

# Register models that use a single-column primary key.
@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    """
    Customize how publishers appear in Django Admin.
    """

    # Display these columns in the publisher list.
    list_display = ("publisherid", "name", "biascategory", "location")

    # Allow administrators to search publishers by name.
    search_fields = ("name",)

    # Add a sidebar filter for political bias category.
    list_filter = ("biascategory",)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """
    Customize the article list and search functionality.
    """

    # Columns displayed in the article list.
    list_display = (
        "articleid",
        "title",
        "publisher_name",
        "datepublished",
        "dateaccessed",
    )

    # Search by article title or publisher name.
    search_fields = ("title", "publisherid__name")

    # Filter by publisher and publication/access dates.
    list_filter = (
        "publisherid",
        "datepublished",
        "dateaccessed",
    )

    # Search for publishers by name when adding an article.
    autocomplete_fields = ("publisherid",)

    @admin.display(description="Publisher", ordering="publisherid__name")
    def publisher_name(self, obj):
        # Display the publisher's name instead of its ID.
        return obj.publisherid.name if obj.publisherid else "Unknown"

class CurrentRevisionStatusFilter(admin.SimpleListFilter):
    """
    Filter stories by the status of their current revision.

    This is separate from Story.status because a published
    story may have a newer Draft or Rejected revision.
    """

    title = "current revision status"
    parameter_name = "current_revision_status"

    def lookups(self, request, model_admin):
        # Options displayed in the Django Admin sidebar.
        return [
            ("Draft", "Draft (Awaiting Review)"),
            ("Rejected", "Rejected (Needs Changes)"),
            ("Published", "Published"),
        ]

    def queryset(self, request, queryset):
        # Return all stories when no filter is selected.
        if self.value() is None:
            return queryset

        # Find stories whose current revision matches the
        # selected status.
        return queryset.filter(
            revisions__revisionnum=F("currentrevisionnum"),
            revisions__status=self.value(),
        )

class PublicationStateFilter(admin.SimpleListFilter):
    """
    Filter stories based on whether they have a published revision.

    A story can have a published revision even when its
    current working revision is Draft or Rejected.
    """

    title = "publication state"
    parameter_name = "publication_state"

    def lookups(self, request, model_admin):
        return [
            ("published", "Has Published Revision"),
            ("unpublished", "Never Published"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "published":
            # Stories with an approved revision.
            return queryset.filter(publishedrevisionnum__isnull=False)

        if self.value() == "unpublished":
            # Stories that have never had an approved revision.
            return queryset.filter(publishedrevisionnum__isnull=True)

        # No publication state filter selected.
        return queryset

class StoryTagFilter(admin.SimpleListFilter):
    """
    Filter stories by their assigned tags.
    """

    title = "story tag"
    parameter_name = "story_tag"

    def lookups(self, request, model_admin):
        # Display all available tags in the filter sidebar.
        return [
            (str(tag.tagid), tag.name)
            for tag in Tag.objects.order_by("name")
        ]

    def queryset(self, request, queryset):
        # Return all stories when no tag is selected.
        if self.value() is None:
            return queryset

        # Find stories associated with the selected tag.
        matching_story_ids = StoryTag.objects.filter(
            tagid_id=self.value()
        ).values("storyid_id")

        return queryset.filter(
            storyid__in=matching_story_ids
        )
    
@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    """
    Customize how stories appear in Django Admin.
    """
    form = StoryAdminForm

    # Custom confirmation pages for permanent story deletion.
    delete_confirmation_template = (
        "admin/stories/delete_confirmation.html"
    )

    delete_selected_confirmation_template = (
        "admin/stories/delete_selected_confirmation.html"
    )

    # Register an action in the Story list's Actions dropdown.
    actions = [
        "approve_revision",
        "archive_selected_stories",
        "restore_selected_stories",
        "delete_selected_stories",
    ]

    # Display story information, including its current headline,
    # so editors can identify stories without opening them.
    list_display = (
        "storyid",
        "current_headline",
        "currentrevisionnum",
        "current_revision_status",
        "status",
        "datecreated",
        "datemodified",
    )

    # Filter by current revision status, overall story status,
    # and creation date.
    list_filter = (
        CurrentRevisionStatusFilter,
        PublicationStateFilter,
        StoryTagFilter,
        "status",
        "datecreated",
    )

    # Keep Django Admin's search bar visible.
    # Actual searching is handled by get_search_results().
    search_fields = ("storyid",)

    # Prevent accidental changes to automatically managed fields.
    readonly_fields = (
        "status",
        "currentrevisionnum",
        "publishedrevisionnum",
        "datecreated",
        "datemodified",
        "current_headline",
        "current_summary",
        "current_sources",
        "published_headline",
        "published_summary",
        "published_sources",
    )

    fieldsets = [
        (
            "Story Information",
            {
                "fields": [
                    "status",
                    "imageurl",
                    "datecreated",
                    "datemodified",
                ],
            },
        ),
        (
            "Story Tags",
            {
                "classes": ["collapse"],
                "fields": ("tags",),
                "description": "Assign categories and topics to this story.",
            },
        ),
        (
            "Current Revision",
            {
                "fields": [
                    "editing_revision",
                    "currentrevisionnum",
                    "current_headline",
                    "current_summary",
                    "current_sources",
                    "review_feedback",
                ],
            },
        ),
        (
            "Published Revision",
            {
                "classes": ["collapse"],
                "fields": [
                    "publishedrevisionnum",
                    "published_headline",
                    "published_summary",
                    "published_sources",
                ],
            },
        ),
    ]

    def get_urls(self):
        """
        Add custom URLs for generating stories and revisions.
        """

        # Preserve Django Admin's existing URLs.
        urls = super().get_urls()

        custom_urls = [
            # Generate a completely new story.
            path(
                "generate/",
                self.admin_site.admin_view(self.generate_story_view),
                name="stories_story_generate",
            ),

            # Generate a new revision for an existing story.
            path(
                "<int:story_id>/generate-revision/",
                self.admin_site.admin_view(self.generate_revision_view),
                name="stories_story_generate_revision",
            ),

            # View all generated revisions of an existing story.
            path(
                "<int:story_id>/revisions/",
                self.admin_site.admin_view(self.revision_history_view),
                name="stories_story_revision_history",
            ),
            # Approve the current revision of a story.
            path(
                "<int:story_id>/approve-revision/",
                self.admin_site.admin_view(self.approve_revision_view),
                name="stories_story_approve_revision",
            ),

            # Reject the current revision and collect feedback.
            path(
                "<int:story_id>/reject-revision/",
                self.admin_site.admin_view(self.reject_revision_view),
                name="stories_story_reject_revision",
            ),
            path(
                "<int:story_id>/regenerate-rejected/",
                self.admin_site.admin_view(self.regenerate_rejected_view),
                name="stories_story_regenerate_rejected",
            ),
            # Archive an existing published story.
            path(
                "<int:story_id>/archive/",
                self.admin_site.admin_view(self.archive_story_view),
                name="stories_story_archive",
            ),

            # Restore an archived story.
            path(
                "<int:story_id>/restore/",
                self.admin_site.admin_view(self.restore_story_view),
                name="stories_story_restore",
            ),

        ]

        # Custom URLs must come before Django's default URLs.
        return custom_urls + urls

    def get_actions(self, request):
        """
        Replace Django's default bulk deletion action with
        our lifecycle-aware deletion action.
        """

        actions = super().get_actions(request)

        # Remove Django's original bulk deletion action.
        actions.pop("delete_selected", None)

        return actions

    def generate_story_view(self, request):
        """
        Collect source articles, generate a story using Gemini,
        and save the resulting story and revision to PostgreSQL.
        """

        if request.method == "POST":
            # Populate the formset with submitted article data.
            formset = ArticleFormSet(request.POST)

            if formset.is_valid():
                articles = []

                # Convert each completed form into the dictionary
                # format expected by our story-generation service.
                for form in formset:
                    if not form.cleaned_data:
                        continue

                    data = form.cleaned_data

                    articles.append({
                        "title": data["title"],
                        "link": data["link"],
                        "publisher_id": data["publisher"].publisherid,
                        "text": data["text"],
                    })

                try:
                    # Gemini generates the headline and summary.
                    # Our service saves the story, revision,
                    # articles, and relationships to PostgreSQL.
                    story = generate_and_save_story(articles)

                except Exception:
                    # Log the full error for debugging without
                    # exposing internal details in the admin page.
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to generate story"
                    )

                    messages.error(
                        request,
                        "Story generation failed. Check the server logs."
                    )

                else:
                    # Display a success notification.
                    messages.success(
                        request,
                        f"Story {story.storyid} generated successfully!"
                    )

                    # Redirect to the newly created Story record.
                    return redirect(
                        reverse(
                            "admin:stories_story_change",
                            args=[story.pk],
                        )
                    )

        else:
            # Display two blank article forms on initial page load.
            formset = ArticleFormSet()

        # Render the page, including any validation errors.
        context = {
            **self.admin_site.each_context(request),
            "title": "Generate New Story",
            "formset": formset,
        }

        return render(
            request,
            "admin/stories/generate_story.html",
            context,
        )

    @admin.display(description="Current Revision Status")
    def current_revision_status(self, obj):
        """
        Display the review status of the story's newest revision.

        This is separate from the Story's publication status.
        A published story may have a newer revision under review.
        """

        if not obj.currentrevisionnum:
            return "No revision available"

        revision = obj.revisions.filter(
            revisionnum=obj.currentrevisionnum
        ).first()

        return revision.status if revision else "No revision available"

    @admin.display(description="Current Headline")
    def current_headline(self, obj):
        """
        Display the headline from the story's current revision.
        """
        if not obj.pk or not obj.currentrevisionnum:
            return "No revision available"

        revision = obj.revisions.filter(
            revisionnum=obj.currentrevisionnum
        ).first()

        return revision.headline if revision else "No revision available"


    @admin.display(description="Current Summary")
    def current_summary(self, obj):
        """
        Display the summary from the story's current revision.
        """
        if not obj.pk or not obj.currentrevisionnum:
            return "No revision available"

        revision = obj.revisions.filter(
            revisionnum=obj.currentrevisionnum
        ).first()

        return revision.summary if revision else "No revision available"

    @admin.display(description="Current Source Articles")
    def current_sources(self, obj):
        """
        Display clickable links to the source articles
        associated with the current story revision.
        """

        if not obj.pk or not obj.currentrevisionnum:
            return "No revision available"

        # Retrieve articles linked to the current revision.
        links = RevisionArticle.objects.filter(
            storyid=obj,
            revisionnum=obj.currentrevisionnum,
        ).select_related("articleid", "articleid__publisherid")

        sources = []

        for link in links:
            article = link.articleid
            publisher = article.publisherid

            # Display the publisher's name alongside the title.
            publisher_name = publisher.name if publisher else "Unknown"

            sources.append((
                article.link or "",
                article.title or "Untitled article",
                publisher_name,
            ))

        if not sources:
            return "No sources available"

        # Generate a clickable link for each article.
        return format_html_join(
            "",
            '<div><a href="{}" target="_blank" rel="noopener noreferrer">{}</a> — {}</div>',
            sources,
        )

    def has_add_permission(self, request):
        """
        Prevent administrators from manually creating Story records.

        Stories should be created through our Generate Story workflow,
        which also creates the initial revision and article links.
        """
        return False

    def has_change_permission(self, request, obj=None):
        """
        Prevent administrators from modifying archived stories.

        Archived stories remain viewable but must be restored
        before any editorial changes can be made.
        """

        # Prevent changes to individual archived stories.
        if obj is not None and obj.status == "Archived":
            return False

        # Preserve Django's normal permission checks.
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """
        Only allow permanent deletion of eligible stories.

        Published stories must be archived before deletion.
        """

        # Preserve Django's normal deletion permission checks.
        if not super().has_delete_permission(request, obj):
            return False

        # Allow model-level permission checks for bulk actions.
        if obj is None:
            return True

        # Enforce our story lifecycle deletion rules.
        return can_delete_story(obj)

    def changeform_view(
        self, request, object_id=None, form_url="", extra_context=None
    ):
        """
        Lock existing stories during form submissions to prevent
        concurrent archiving or editorial changes.
        """

        # Viewing a story does not require a database lock.
        if request.method != "POST" or object_id is None:
            return super().changeform_view(
                request, object_id, form_url, extra_context
            )

        with transaction.atomic():

            # Lock the story before Django retrieves it and checks
            # whether the administrator has permission to modify it.
            Story.objects.select_for_update().filter(
                pk=object_id
            ).first()

            # Process the form while holding the story lock.
            return super().changeform_view(
                request, object_id, form_url, extra_context
            )

    def delete_model(self, request, obj):
        """
        Delete an individual story using our custom deletion service.
        """
        delete_story(obj.pk)

    def delete_queryset(self, request, queryset):
        """
        Delete multiple selected stories using our custom deletion service.

        If any deletion fails, roll back the entire operation.
        """
        with transaction.atomic():
            # Collect story IDs before modifying the database.
            story_ids = list(
                queryset.order_by("pk").values_list("pk", flat=True)
            )

            # Safely delete each selected story.
            for story_id in story_ids:
                delete_story(story_id)

    def generate_revision_view(self, request, story_id):
        """
        Generate a new revision of an existing story using
        the current source articles and Gemini.
        """

        # Retrieve the existing story.
        story = self.get_object(request, str(story_id))

        if story is None:
            raise Http404("Story not found")

        if request.method == "POST":
            # Populate the forms with submitted article data.
            formset = ArticleFormSet(request.POST)

            if formset.is_valid():
                articles = []

                # Convert completed forms into the format
                # expected by our revision-generation service.
                for form in formset:
                    if not form.cleaned_data:
                        continue

                    data = form.cleaned_data

                    articles.append({
                        "title": data["title"],
                        "link": data["link"],
                        "publisher_id": data["publisher"].publisherid,
                        "text": data["text"],
                    })

                try:
                    # Generate a new revision for the existing story.
                    # This preserves the previous revisions.
                    revision = generate_and_save_revision(
                        story_id,
                        articles,
                    )

                except Exception:
                    # Record the error without exposing sensitive
                    # information to the administrator.
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to generate revision for Story %s",
                        story_id,
                    )

                    messages.error(
                        request,
                        "Revision generation failed. Check the server logs.",
                    )

                else:
                    # Notify the administrator of the new revision.
                    messages.success(
                        request,
                        f"Revision {revision.revisionnum} "
                        f"generated successfully for Story {story_id}!",
                    )

                    # Return to the existing Story edit page.
                    return redirect(
                        reverse(
                            "admin:stories_story_change",
                            args=[story_id],
                        )
                    )

        else:
            # Display two blank article forms initially.
            formset = ArticleFormSet()

        # Render the form and display any validation errors.
        context = {
            **self.admin_site.each_context(request),
            "title": f"Generate Revision for Story {story_id}",
            "story": story,
            "formset": formset,
        }

        return render(
            request,
            "admin/stories/generate_revision.html",
            context,
        )

    def revision_history_view(self, request, story_id):
        """
        Display every generated revision for an existing story.
        """

        from django.http import Http404

        # Retrieve the story and verify it exists.
        story = self.get_object(request, str(story_id))

        if story is None:
            raise Http404("Story not found")

        # Retrieve all revisions, newest first.
        revisions = list(
            StoryRevision.objects.filter(
                storyid=story
            ).order_by("-revisionnum")
        )

        # Retrieve article links for every revision of this story.
        links = RevisionArticle.objects.filter(
            storyid=story
        ).select_related(
            "articleid",
            "articleid__publisherid",
        )

        # Group source articles by their revision number.
        sources_by_revision = {}

        for link in links:
            sources_by_revision.setdefault(
                link.revisionnum, []
            ).append(link.articleid)

        # Attach the corresponding sources to each revision.
        # This is only for displaying the page; nothing is saved.
        for revision in revisions:
            revision.source_articles = sources_by_revision.get(
                revision.revisionnum, []
            )

        # Pass the story and its revisions to our template.
        context = {
            **self.admin_site.each_context(request),
            "title": f"Revision History for Story {story_id}",
            "story": story,
            "revisions": revisions,
        }

        return render(
            request,
            "admin/stories/revision_history.html",
            context,
        )

    @admin.action(description="Approve selected story revisions")
    def approve_revision(self, request, queryset):
        """
        Approve the current revision of each selected story.

        The approved revision becomes the publicly visible version.
        Previously published revisions remain in revision history.
        """

        approved = 0

        for story in queryset:
            with transaction.atomic():
                # Lock the story to prevent concurrent approval updates.
                locked_story = Story.objects.select_for_update().get(
                    pk=story.pk
                )

                # Find the current revision.
                revision = locked_story.revisions.filter(
                    revisionnum=locked_story.currentrevisionnum
                ).first()

                # Archived stories must be restored before approving revisions.
                if locked_story.status == "Archived":
                    continue

                # Only Draft revisions can be approved.
                if revision is None or revision.status != "Draft":
                    continue

                # Mark this revision as approved.
                revision.status = "Published"
                revision.save(update_fields=["status"])

                # Make this revision the public version of the story.
                locked_story.publishedrevisionnum = revision.revisionnum
                locked_story.status = "Published"

                locked_story.save(
                    update_fields=["publishedrevisionnum", "status"]
                )

                approved += 1

                # Collect article IDs associated with the approved revision.
                article_ids = list(
                    RevisionArticle.objects.filter(
                        storyid=locked_story,
                        revisionnum=revision.revisionnum,
                    ).values_list("articleid_id", flat=True)
                )

                # Clean up these articles after approval commits.
                transaction.on_commit(
                    lambda ids=article_ids: cleanup_unused_article_text(ids)
                )

        self.message_user(
            request,
            f"{approved} story revision(s) approved and published.",
            messages.SUCCESS,
        )

    @admin.action(
        permissions=["change"],
        description="Archive selected stories",
    )
    def archive_selected_stories(self, request, queryset):
        """
        Archive selected published stories while preserving
        their revisions and associated metadata.
        """

        archived = 0
        skipped = 0

        for story in queryset:
            try:
                # Archive the story using the existing service.
                archive_story(story.pk)
                archived += 1

            except (ValueError, Story.DoesNotExist):
                # Skip stories that are no longer eligible or available.
                skipped += 1

        if archived:
            self.message_user(
                request,
                f"{archived} story(s) successfully archived.",
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"{skipped} story(s) skipped because they could not be archived.",
                messages.WARNING,
            )

    @admin.action(
        permissions=["change"],
        description="Restore selected stories",
    )
    def restore_selected_stories(self, request, queryset):
        """
        Restore selected archived stories to their published state.
        """

        restored = 0
        skipped = 0

        for story in queryset:
            try:
                # Restore the story using the existing service.
                restore_story(story.pk)
                restored += 1

            except (ValueError, Story.DoesNotExist):
                # Skip stories that are no longer eligible or available.
                skipped += 1

        if restored:
            self.message_user(
                request,
                f"{restored} story(s) successfully restored.",
                messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"{skipped} story(s) skipped because they could not be restored.",
                messages.WARNING,
            )

    @admin.action(
        permissions=["delete"],
        description="Delete selected stories",
    )
    def delete_selected_stories(self, request, queryset):
        """
        Permanently delete eligible selected stories while
        skipping stories that cannot be deleted.
        """

        with transaction.atomic():

            # Determine whether the administrator confirmed deletion.
            confirmed = request.POST.get("post") == "yes"

            # Lock the selected stories during confirmed deletion.
            if confirmed:
                queryset = queryset.select_for_update()

            eligible_ids = []
            skipped_stories = []

            # Evaluate stories in a consistent order.
            for story in queryset.order_by("pk"):
                if self.has_delete_permission(request, story):
                    eligible_ids.append(story.pk)
                else:
                    skipped_stories.append(story)

            # Stop if none of the selected stories can be deleted.
            if not eligible_ids:
                self.message_user(
                    request,
                    "None of the selected stories are eligible for deletion. "
                    "Published stories must be archived first.",
                    messages.WARNING,
                )
                return None

            # Pass only eligible stories to Django's deletion action.
            eligible_queryset = queryset.filter(pk__in=eligible_ids)

            response = delete_selected(
                self, request, eligible_queryset
            )

            # Add skipped stories to the confirmation page.
            if not confirmed and response is not None:
                response.context_data["skipped_stories"] = skipped_stories
                response.context_data["skipped_count"] = len(skipped_stories)
                response.context_data["eligible_count"] = len(eligible_ids)

                # Preserve the custom action for the confirmation POST.
                response.context_data["bulk_delete_action"] = (
                    "delete_selected_stories"
                )

            # Report stories skipped during confirmed deletion.
            elif confirmed and skipped_stories:
                self.message_user(
                    request,
                    f"{len(skipped_stories)} story(s) skipped because "
                    "they were not eligible for deletion.",
                    messages.WARNING,
                )

            return response

    def approve_revision_view(self, request, story_id):
        """
        Approve the current revision of a story from its Admin page.
        Only POST requests can change the database.
        """
        from django.http import Http404, HttpResponseNotAllowed

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        with transaction.atomic():
            # Lock the story while processing approval.
            story = Story.objects.select_for_update().filter(
                pk=story_id
            ).first()

            if story is None:
                raise Http404("Story not found")

            # Prevent approval of revisions belonging to archived stories.
            if story.status == "Archived":
                messages.error(
                    request,
                    "Archived stories must be restored before approving revisions."
                )

                return redirect(
                    reverse("admin:stories_story_change", args=[story_id])
                )

            # Retrieve the current revision.
            revision = story.revisions.filter(
                revisionnum=story.currentrevisionnum
            ).first()

            # Only Draft revisions can be approved.
            if revision is None or revision.status != "Draft":
                messages.error(
                    request,
                    "Only Draft revisions can be approved."
                )
            else:
                # Publish the approved revision.
                revision.status = "Published"
                revision.save(update_fields=["status"])

                # Update the publicly visible revision.
                story.publishedrevisionnum = revision.revisionnum
                story.status = "Published"

                story.save(
                    update_fields=["publishedrevisionnum", "status"]
                )

                # Collect article IDs associated with the approved revision.
                article_ids = list(
                    RevisionArticle.objects.filter(
                        storyid=story,
                        revisionnum=revision.revisionnum,
                    ).values_list("articleid_id", flat=True)
                )

                # Clean up these articles after approval commits.
                transaction.on_commit(
                    lambda ids=article_ids: cleanup_unused_article_text(ids)
                )

                messages.success(
                    request,
                    f"Revision {revision.revisionnum} approved "
                    f"for Story {story_id}!"
                )

        # Return to the Story edit page.
        return redirect(
            reverse(
                "admin:stories_story_change",
                args=[story_id],
            )
        )

    def reject_revision_view(self, request, story_id):
        """
        Allow an administrator to reject the current revision
        after providing mandatory feedback.
        """
        from django.http import Http404
        from django.shortcuts import get_object_or_404

        story = get_object_or_404(Story, pk=story_id)

        # Prevent archived stories from entering the rejection workflow.
        if story.status == "Archived":
            messages.error(
                request,
                "Archived stories must be restored before rejecting revisions."
            )

            return redirect(
                reverse("admin:stories_story_change", args=[story_id])
            )

        revision = story.revisions.filter(
            revisionnum=story.currentrevisionnum
        ).first()

        if revision is None:
            raise Http404("Current revision not found")

        # Only Draft revisions can be rejected.
        if revision.status != "Draft":
            messages.error(
                request,
                "Only Draft revisions can be rejected."
            )
            return redirect(
                reverse("admin:stories_story_change", args=[story_id])
            )

        if request.method == "POST":
            form = RevisionRejectionForm(request.POST)

            if form.is_valid():
                with transaction.atomic():
                    # Lock the story to prevent concurrent updates.
                    story = Story.objects.select_for_update().get(
                        pk=story_id
                    )

                    # Recheck the status in case the story was archived
                    # while the administrator was completing the rejection form.
                    if story.status == "Archived":
                        messages.error(
                            request,
                            "This story has been archived and cannot be rejected."
                        )

                        return redirect(
                            reverse("admin:stories_story_change", args=[story_id])
                        )

                    # Recheck the revision after acquiring the lock.
                    revision = story.revisions.get(
                        revisionnum=story.currentrevisionnum
                    )

                    if revision.status != "Draft":
                        messages.error(
                            request,
                            "This revision is no longer a Draft."
                        )
                        return redirect(
                            reverse(
                                "admin:stories_story_change",
                                args=[story_id]
                            )
                        )

                    # Save the rejection and its feedback.
                    revision.status = "Rejected"
                    revision.reviewfeedback = form.cleaned_data["feedback"]

                    revision.save(
                        update_fields=["status", "reviewfeedback"]
                    )

                    # Keep previously published stories visible.
                    if story.publishedrevisionnum is None:
                        story.status = "Changes Needed"
                        story.save(update_fields=["status"])

                messages.success(
                    request,
                    f"Revision {revision.revisionnum} rejected. "
                    "Feedback saved successfully."
                )

                return redirect(
                    reverse("admin:stories_story_change", args=[story_id])
                )

        else:
            form = RevisionRejectionForm()

        context = {
            **self.admin_site.each_context(request),
            "title": f"Reject Revision for Story {story_id}",
            "story": story,
            "revision": revision,
            "form": form,
        }

        return render(
            request,
            "admin/stories/reject_revision.html",
            context,
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        Provide the current revision's status to the Story edit template.
        """
        extra_context = extra_context or {}

        story = self.get_object(request, object_id)

        if story and story.currentrevisionnum:
            revision = story.revisions.filter(
                revisionnum=story.currentrevisionnum
            ).first()

            extra_context["current_revision_status"] = (
                revision.status if revision else None
            )
            # Provide the current revision's feedback to the editable form.
            extra_context["current_review_feedback"] = (
                revision.reviewfeedback if revision else ""
            )
            # Check normal change permissions independently of archive restrictions.
            extra_context["can_manage_archive"] = (
                story is not None
                and super().has_change_permission(request, story)
            )

        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

    def regenerate_rejected_view(self, request, story_id):
        """
        Regenerate a rejected revision using editorial feedback.

        Creates a new Draft revision without modifying the
        previously published revision.
        """

        # Regeneration changes database records, so require POST.
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        try:
            # Generate a new revision using the rejected revision's
            # original articles, headline, summary, and feedback.
            revision = regenerate_rejected_revision(story_id)

        except Story.DoesNotExist:
            messages.error(request, "Story not found.")

        except ValueError as error:
            # Handle invalid revision status or missing feedback.
            messages.error(request, str(error))

        except Exception:
            # Log unexpected errors for debugging without exposing
            # internal details to the administrator.
            logger.exception(
                "Failed to regenerate rejected revision for story %s",
                story_id,
            )
            messages.error(
                request,
                "Regeneration failed. Check the server logs for details.",
            )

        else:
            messages.success(
                request,
                f"Revision {revision.revisionnum} generated successfully "
                "and saved as Draft.",
            )

        # Return to the Story edit page.
        return redirect("admin:stories_story_change", story_id)

    @admin.display(description="Current Revision Review Feedback")
    def current_review_feedback(self, obj):
        """
        Display feedback associated with the current revision.
        """

        # A story without revisions cannot have review feedback.
        if not obj.currentrevisionnum:
            return "No revision available"

        # Retrieve the current revision.
        revision = obj.revisions.filter(
            revisionnum=obj.currentrevisionnum
        ).first()

        # Display the feedback if it exists.
        if revision and revision.reviewfeedback:
            return revision.reviewfeedback

        return "No review feedback available"

    def archive_story_view(self, request, story_id):
        """
        Archive a published story while preserving its revisions,
        source articles, and associated metadata.
        """

        # Only POST requests can modify the database.
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        # Retrieve the requested story.
        story = self.get_object(request, str(story_id))

        if story is None:
            raise Http404("Story not found")

        # Require the administrator's normal change permission.
        if not super().has_change_permission(request, story):
            raise PermissionDenied

        try:
            # Archive the story using the existing service.
            archive_story(story_id)

            messages.success(
                request,
                f"Story {story_id} was successfully archived."
            )

        except ValueError as error:
            messages.error(request, str(error))

        except Story.DoesNotExist:
            raise Http404("Story not found")

        # Return to the Story page.
        return redirect(
            reverse("admin:stories_story_change", args=[story_id])
        )

    def restore_story_view(self, request, story_id):
        """
        Restore an archived story to its published state.
        """

        # Only POST requests can modify the database.
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        # Retrieve the requested story.
        story = self.get_object(request, str(story_id))

        if story is None:
            raise Http404("Story not found")

        # Check the underlying change permission because our
        # overridden method prevents changes to archived stories.
        if not super().has_change_permission(request, story):
            raise PermissionDenied

        try:
            # Restore the story using the existing service.
            restore_story(story_id)

            messages.success(
                request,
                f"Story {story_id} was successfully restored."
            )

        except ValueError as error:
            messages.error(request, str(error))

        except Story.DoesNotExist:
            raise Http404("Story not found")

        # Return to the Story page.
        return redirect(
            reverse("admin:stories_story_change", args=[story_id])
        )

    def save_model(self, request, obj, form, change):
        """
        Save the Story and update the current rejected revision's
        review feedback when it has been edited.
        """

        # Save the Story normally.
        super().save_model(request, obj, form, change)

        # Only update feedback when the field was changed.
        if "review_feedback" not in form.changed_data:
            return

        # Retrieve the current revision.
        revision = StoryRevision.objects.filter(
            storyid=obj,
            revisionnum=obj.currentrevisionnum,
            status="Rejected",
        ).first()

        # Only rejected revisions can have their feedback updated.
        if revision is None:
            return

        # Save the edited feedback to the StoryRevision table.
        revision.reviewfeedback = form.cleaned_data["review_feedback"]
        revision.save(update_fields=["reviewfeedback"])

    def published_headline(self, obj):
        """
        Display the headline of the currently published revision.
        """

        # A story without a published revision has nothing to display.
        if not obj.publishedrevisionnum:
            return "No published revision available"

        # Retrieve the revision currently visible to readers.
        revision = obj.revisions.filter(
            revisionnum=obj.publishedrevisionnum
        ).first()

        return revision.headline if revision else "No published revision available"

    published_headline.short_description = "Published Headline"

    @admin.display(description="Published Summary")
    def published_summary(self, obj):
        """
        Display the summary of the currently published revision.
        """

        # A story without a published revision has nothing to display.
        if not obj.publishedrevisionnum:
            return "No published revision available"

        # Retrieve the revision currently visible to readers.
        revision = obj.revisions.filter(
            revisionnum=obj.publishedrevisionnum
        ).first()

        return revision.summary if revision else "No published revision available"

    @admin.display(description="Published Source Articles")
    def published_sources(self, obj):
        """
        Display source articles associated with the currently
        published revision.
        """

        # A story may not have a published revision yet.
        if not obj.publishedrevisionnum:
            return "No published revision available"

        # Retrieve articles linked to the published revision.
        links = (
            RevisionArticle.objects
            .filter(
                storyid=obj,
                revisionnum=obj.publishedrevisionnum,
            )
            .select_related("articleid", "articleid__publisherid")
        )

        # Build clickable article links with their publisher names.
        articles = [
            format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a> — {}',
                link.articleid.link,
                link.articleid.title,
                (
                    link.articleid.publisherid.name
                    if link.articleid.publisherid
                    else "Unknown Publisher"
                ),
            )
            for link in links
        ]

        if not articles:
            return "No source articles found"

        return format_html_join(
            mark_safe("<br>"),
            "{}",
            ((article,) for article in articles),
        )

    def get_fieldsets(self, request, obj=None):
        """
        Display the current revision's status and the published
        revision's number in their respective fieldset headings.
        """

        # Get the existing fieldsets without modifying the originals.
        fieldsets = list(super().get_fieldsets(request, obj))

        if not obj:
            return fieldsets

        # Retrieve the current revision's status.
        current_status = None

        if obj.currentrevisionnum:
            revision = obj.revisions.filter(
                revisionnum=obj.currentrevisionnum
            ).first()

            if revision:
                current_status = revision.status

        # Update the fieldset headings.
        updated_fieldsets = []

        # Review feedback is only relevant for rejected revisions.
        show_feedback = current_status == "Rejected"

        for name, options in fieldsets:

            # Copy the fieldset options so we don't modify the
            # original fieldsets shared across Admin requests.
            options = options.copy()

            # Hide the feedback field unless the current revision is rejected.
            if name == "Current Revision" and not show_feedback:
                options["fields"] = [
                    field
                    for field in options["fields"]
                    if field != "review_feedback"
                ]

            if name == "Current Revision" and current_status:
                name = f"Current Revision ({current_status})"

            elif name == "Published Revision":
                if obj.publishedrevisionnum is not None:
                    name = f"Published Revision ({obj.publishedrevisionnum})"
                else:
                    name = "Published Revision (None)"

            updated_fieldsets.append((name, options))

        return updated_fieldsets

    def get_search_results(self, request, queryset, search_term):
        """
        Search stories by their Story ID or current revision headline.

        Only search the current revision's headline, not
        headlines belonging to historical revisions.
        """

        # Return all stories when the search field is empty.
        if not search_term:
            return queryset, False

        # Find stories whose current revision headline contains
        # the entered search term.
        matching_stories = StoryRevision.objects.filter(
            revisionnum=F("storyid__currentrevisionnum"),
            headline__icontains=search_term,
        ).values("storyid_id")

        # Search by Story ID when the entered value is numeric.
        if search_term.isdigit():
            queryset = queryset.filter(
                Q(storyid=int(search_term)) |
                Q(storyid__in=matching_stories)
            )
        else:
            queryset = queryset.filter(
                storyid__in=matching_stories
            )

        return queryset, False

    def save_related(self, request, form, formsets, change):
        """
        Save the story's tag relationships after the story itself
        has been saved.

        Preserve existing relationships, add newly selected tags,
        and remove tags that were deselected.
        """

        # Allow Django Admin to save its normal related objects first.
        super().save_related(request, form, formsets, change)

        # Get the IDs of all tags selected in the form.
        selected_tag_ids = {
            tag.pk for tag in form.cleaned_data["tags"]
        }

        # Get the IDs of tags currently assigned to this story.
        existing_tag_ids = set(
            StoryTag.objects.filter(
                storyid=form.instance
            ).values_list("tagid_id", flat=True)
        )

        # Create relationships for newly selected tags.
        for tag_id in selected_tag_ids - existing_tag_ids:
            StoryTag.objects.create(
                storyid=form.instance,
                tagid_id=tag_id,
            )

        # Remove relationships for deselected tags.
        StoryTag.objects.filter(
            storyid=form.instance,
            tagid_id__in=existing_tag_ids - selected_tag_ids,
        ).delete()
    
# Customize Django Admin branding for Reel News.

# Text displayed in the top-left header.
admin.site.site_header = "Reel News Administration"

# Text displayed in the browser tab.
admin.site.site_title = "Reel News Admin"

# Heading displayed on the Admin homepage.
admin.site.index_title = "Reel News Management"