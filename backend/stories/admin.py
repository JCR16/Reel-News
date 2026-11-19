from django.contrib import admin, messages
from .models import Publisher, Article, Story, StoryRevision, RevisionArticle

from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html_join

from .services.story_manager import (
    generate_and_save_story,
    generate_and_save_revision,
)

from .forms import ArticleFormSet

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
    
@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    """
    Customize how stories appear in Django Admin.
    """

    # Display useful story information.
    list_display = (
        "storyid",
        "currentrevisionnum",
        "status",
        "datecreated",
        "datemodified",
    )

    # Filter stories by publication status and creation date.
    list_filter = ("status", "datecreated")

    # Search for a story using its ID.
    search_fields = ("=storyid",)

    # Prevent accidental changes to automatically managed fields.
    readonly_fields = (
        "currentrevisionnum",
        "datecreated",
        "datemodified",
        "current_headline",
        "current_summary",
        "current_sources",
    )

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
        ]

        # Custom URLs must come before Django's default URLs.
        return custom_urls + urls


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

    def generate_revision_view(self, request, story_id):
        """
        Generate a new revision of an existing story using
        the current source articles and Gemini.
        """

        # Retrieve the existing story.
        story = self.get_object(request, str(story_id))

        if story is None:
            from django.http import Http404
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

    
# Customize Django Admin branding for Reel News.

# Text displayed in the top-left header.
admin.site.site_header = "Reel News Administration"

# Text displayed in the browser tab.
admin.site.site_title = "Reel News Admin"

# Heading displayed on the Admin homepage.
admin.site.index_title = "Reel News Management"