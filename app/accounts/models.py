from django.conf import settings
from django.db import models


class Bookmark(models.Model):
    """
    Represents a story saved by an authenticated user.

    Bookmarks reference stories rather than individual revisions,
    allowing them to persist across editorial updates.
    """

    # Prevent duplicate bookmarks for the same user and story.
    pk = models.CompositePrimaryKey("userid", "storyid")

    # Identify the user who saved the story.
    userid = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="userID",
        related_name="bookmarks",
    )

    # Identify the saved story.
    storyid = models.ForeignKey(
        "stories.Story",
        on_delete=models.CASCADE,
        db_column="storyID",
        related_name="bookmarks",
    )

    # Record when the bookmark was created.
    datecreated = models.DateTimeField(
        auto_now_add=True,
        db_column="dateCreated",
    )

    class Meta:
        managed = False
        db_table = "bookmark"

    def __str__(self):
        return f"User {self.userid_id} - Story {self.storyid_id}"