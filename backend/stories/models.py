# Reel News - Database Models
#
# Developed by: Reel News team
# Description: Defines Django ORM models for the Story and
# StoryRevision tables in the team's PostgreSQL database.
#
# Database schema:
# - Designed and implemented by the Reel News team.
# - Django models map to existing PostgreSQL tables.
# - managed=False prevents Django from managing these tables.
#
# External libraries:
# - Django ORM: Model definitions, fields, and relationships.
#
# External code:
# - No third-party source code was copied or adapted.

from django.db import models

class Story(models.Model):
    storyid = models.AutoField(
        db_column="storyID",
        primary_key=True,
    )
    currentrevisionnum = models.IntegerField(
        db_column="currentRevisionNum",
        blank=True,
        null=True,
    )
    publishedrevisionnum = models.IntegerField(
        db_column="publishedRevisionNum",
        blank=True,
        null=True
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
    related_name="revisions",
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
    status = models.CharField(
        max_length=20,
        default="Draft"
    )
    reviewfeedback = models.TextField(
        db_column="reviewFeedback",
        blank=True,
        null=True
    )

    class Meta:
        managed = False
        db_table = "story_revision"



class Publisher(models.Model):
    publisherid = models.AutoField(
        db_column="publisherID",
        primary_key=True,
    )
    name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    logourl = models.TextField(
        db_column="logoURL",
        blank=True,
        null=True,
    )
    landingpage = models.TextField(
        db_column="landingPage",
        blank=True,
        null=True,
    )
    biascategory = models.CharField(
        db_column="biasCategory",
        max_length=20,
        blank=True,
        null=True,
    )
    biassource = models.TextField(
        db_column="biasSource",
        blank=True,
        null=True,
    )

    def __str__(self):
        # Display the publisher's name instead of "Publisher object (ID)".
        return self.name or f"Publisher {self.publisherid}"


    class Meta:
        managed = False
        db_table = "publisher"



class Article(models.Model):
    articleid = models.AutoField(
        db_column="articleID",
        primary_key=True,
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    link = models.TextField(blank=True, null=True)
    dateaccessed = models.DateTimeField(
        db_column="dateAccessed",
        blank=True,
        null=True,
    )
    datepublished = models.DateTimeField(
        db_column="datePublished",
        blank=True,
        null=True,
    )
    lastchecked = models.DateTimeField(
        db_column="lastChecked",
        blank=True,
        null=True,
    )
    hash = models.CharField(max_length=64, blank=True, null=True)
    publisherid = models.ForeignKey(
        Publisher,
        models.DO_NOTHING,
        db_column="publisherID",
        related_name="articles",
        blank=True,
        null=True,
    )
    biascategory = models.CharField(
        db_column="biasCategory",
        max_length=20,
        blank=True,
        null=True,
    )
    biassource = models.TextField(
        db_column="biasSource",
        blank=True,
        null=True,
    )
    aibiasscore = models.FloatField(
        db_column="aiBiasScore",
        blank=True,
        null=True,
    )

    class Meta:
        managed = False
        db_table = "article"

        

class RevisionArticle(models.Model):
    pk = models.CompositePrimaryKey(
        "articleid", "storyid", "revisionnum"
    )

    articleid = models.ForeignKey(
        Article,
        models.DO_NOTHING,
        db_column="articleID",
        related_name="revision_links",
    )
    storyid = models.ForeignKey(
        Story,
        models.DO_NOTHING,
        db_column="storyID",
    )
    revisionnum = models.IntegerField(
        db_column="revisionNum",
    )

    class Meta:
        managed = False
        db_table = "revision_article"



class ArticleText(models.Model):
    articleid = models.OneToOneField(
        Article,
        models.CASCADE,
        db_column="articleID",
        primary_key=True
    )
    text = models.TextField()

    class Meta:
        managed = False
        db_table = "article_text"

class Tag(models.Model):
    """
    Represents a category or topic that can be assigned to stories.

    Examples: Politics, Technology, World News.
    """

    # PostgreSQL automatically generates unique tag IDs.
    tagid = models.AutoField(
        db_column="tagID",
        primary_key=True,
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    def __str__(self):
        # Display the tag name in Django Admin.
        return self.name or f"Tag {self.tagid}"

    class Meta:
        managed = False
        db_table = "tag"

class StoryTag(models.Model):
    """
    Junction table connecting stories and tags.

    A story can have multiple tags, and the same tag
    can be assigned to multiple stories.
    """

    # Prevent duplicate story/tag combinations.
    pk = models.CompositePrimaryKey("storyid", "tagid")

    storyid = models.ForeignKey(
        Story,
        models.DO_NOTHING,
        db_column="storyID",
        related_name="tag_links",
    )

    tagid = models.ForeignKey(
        Tag,
        models.DO_NOTHING,
        db_column="tagID",
        related_name="story_links",
    )

    class Meta:
        managed = False
        db_table = "story_tag"