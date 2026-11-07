from django.db import models


class Story(models.Model):
    storyid = models.IntegerField(
        db_column="storyID",
        primary_key=True,
    )
    currentrevisionnum = models.IntegerField(
        db_column="currentRevisionNum",
        blank=True,
        null=True,
    )
    datecreated = models.DateTimeField(
        db_column="dateCreated",
        blank=True,
        null=True,
    )
    datemodified = models.DateTimeField(
        db_column="dateModified",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )
    imageurl = models.URLField(
        db_column="imageURL",
        max_length=2048,
        blank=True,
        null=True
    )

    class Meta:
        managed = False
        db_table = "story"


class StoryRevision(models.Model):
    pk = models.CompositePrimaryKey("storyid", "revisionnum")

    storyid = models.ForeignKey(
        Story,
        models.DO_NOTHING,
        db_column="storyID",
    )
    revisionnum = models.IntegerField(db_column="revisionNum")
    datecreated = models.DateTimeField(
        db_column="dateCreated",
        blank=True,
        null=True,
    )
    headline = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    changenote = models.TextField(
        db_column="changeNote",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "story_revision"
