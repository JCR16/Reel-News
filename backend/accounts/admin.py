from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import Bookmark
from stories.models import StoryRevision


class AccountUserAdmin(UserAdmin):
    """
    Extends Django's built-in User administration
    with Reel News account information.
    """

    # Preserve the existing columns and add a bookmark count.
    list_display = UserAdmin.list_display + ("bookmark_count",)

    # Preserve existing read-only fields.
    readonly_fields = UserAdmin.readonly_fields + ("bookmark_list",)

    # Add a separate Bookmarks section to the User detail page.
    # Preserve Django's default fieldsets, but collapse
    # less frequently accessed sections by default.
    fieldsets = tuple(
        (
            name,
            {
                **options,
                "classes": (*options.get("classes", ()), "collapse"),
            }
            if name in ("Permissions", "Important dates")
            else options,
        )
        for name, options in UserAdmin.fieldsets
    ) + (
        ("Bookmarks", {
            "fields": ("bookmark_list",),
        }),
    )

    def get_queryset(self, request):
        """
        Retrieve users and calculate their bookmark counts
        in a single database query.
        """

        queryset = super().get_queryset(request)

        return queryset.annotate(
            total_bookmarks=Count("bookmarks__storyid", distinct=True)
        )
        
    @admin.display(
        description="Bookmarks",
        ordering="total_bookmarks",
    )
    def bookmark_count(self, obj):
        return obj.total_bookmarks

    @admin.display(description="Saved stories")
    def bookmark_list(self, obj):
        """
        Display a scrollable, read-only list of the user's
        bookmarks, including published headlines.
        """

        # Unsaved users cannot have bookmarks.
        if not obj or not obj.pk:
            return "No bookmarks."

        # Retrieve bookmarks and their associated stories.
        bookmarks = list(
            Bookmark.objects.filter(userid=obj)
            .select_related("storyid")
            .order_by("-datecreated", "storyid_id")
        )

        bookmark_count = len(bookmarks)

        if bookmark_count == 0:
            return "0 bookmarks — No saved stories."

        # Identify the published revision of each bookmarked story.
        revision_keys = [
            (bookmark.storyid_id, bookmark.storyid.publishedrevisionnum)
            for bookmark in bookmarks
            if bookmark.storyid.publishedrevisionnum is not None
        ]

        # Retrieve all relevant published revisions in one query.
        revisions = StoryRevision.objects.filter(pk__in=revision_keys)

        # Map each composite primary key to its headline.
        headlines = {
            revision.pk: revision.headline
            for revision in revisions
        }

        # Generate a scrollable list of bookmarks.
        return format_html(
            """
            <div>
                <strong>Total bookmarks: {}</strong>
                <div style="max-height: 250px; overflow-y: auto;
                            margin-top: 8px;">
                    <ul>{}</ul>
                </div>
            </div>
            """,
            bookmark_count,
            format_html_join(
                "",
                """
                <li style="margin-bottom: 10px;">
                    <a href="{}">Story #{} — {}</a>
                    <br>
                    <small>{} · Bookmarked {}</small>
                </li>
                """,
                (
                    (
                        reverse(
                            "admin:stories_story_change",
                            args=[bookmark.storyid_id],
                        ),
                        bookmark.storyid_id,
                        headlines.get(
                            (
                                bookmark.storyid_id,
                                bookmark.storyid.publishedrevisionnum,
                            ),
                            "Published headline unavailable",
                        ),
                        bookmark.storyid.status,
                        bookmark.datecreated.strftime("%Y-%m-%d %H:%M UTC"),
                    )
                    for bookmark in bookmarks
                ),
            ),
        )


# Replace Django's default User admin with our extended version.
admin.site.unregister(User)
admin.site.register(User, AccountUserAdmin)