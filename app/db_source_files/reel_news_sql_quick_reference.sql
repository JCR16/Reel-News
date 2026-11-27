-- REEL NEWS: POSTGRESQL QUICK REFERENCE
-- Replace every <placeholder> before execution.
-- Text placeholders stay in single quotes; numeric placeholders do not.
-- These are templates. Do not execute the entire file at once.
-- Quoted camelCase identifiers must retain their double quotes.

-- ============================================================
-- 1. PUBLISHER
-- ============================================================
-- Add a publisher (publisherID is generated automatically).
INSERT INTO publisher (name, location, "logoURL", "landingPage", "biasCategory", "biasSource")
VALUES ('<publisher_name>', '<location>', '<logo_url>', '<landing_page>', '<bias_category>', '<bias_source>');

-- View all publishers / find one by ID.
SELECT * FROM publisher;
SELECT * FROM publisher WHERE "publisherID" = <publisher_id>;

-- Update a publisher.
UPDATE publisher
SET name = '<new_name>', location = '<new_location>',
    "logoURL" = '<new_logo_url>', "landingPage" = '<new_landing_page>',
    "biasCategory" = '<new_bias_category>', "biasSource" = '<new_bias_source>'
WHERE "publisherID" = <publisher_id>;

-- Delete a publisher only after dependent articles are removed or reassigned.
DELETE FROM publisher WHERE "publisherID" = <publisher_id>;


-- ============================================================
-- 2. ARTICLE
-- ============================================================
-- Add an article. Its publisher must already exist.
INSERT INTO article (title, link, "dateAccessed", "datePublished", "lastChecked",
                     hash, "publisherID", "biasCategory", "biasSource", "aiBiasScore")
VALUES ('<original_title>', '<original_article_url>', '<accessed_timestamp>',
        '<published_timestamp>', '<last_checked_timestamp>', '<64_character_hash>',
        <publisher_id>, '<bias_category>', '<bias_source>', <ai_bias_score>);

-- View all articles / find one by ID / view articles from a publisher.
SELECT * FROM article;
SELECT * FROM article WHERE "articleID" = <article_id>;
SELECT * FROM article WHERE "publisherID" = <publisher_id>;

-- Update an article.
UPDATE article
SET title = '<new_title>', link = '<new_url>',
    "lastChecked" = '<new_last_checked_timestamp>', hash = '<new_64_character_hash>',
    "biasCategory" = '<new_bias_category>', "biasSource" = '<new_bias_source>',
    "aiBiasScore" = <new_ai_bias_score>
WHERE "articleID" = <article_id>;

-- Delete an article only after removing its dependent associations.
DELETE FROM article WHERE "articleID" = <article_id>;


-- ============================================================
-- 3. AUTHOR
-- ============================================================
-- Add an author (authorID is generated automatically).
INSERT INTO author ("firstName", "lastName")
VALUES ('<first_name>', '<last_name>');

-- View all authors / find one by ID.
SELECT * FROM author;
SELECT * FROM author WHERE "authorID" = <author_id>;

-- Update an author.
UPDATE author
SET "firstName" = '<new_first_name>', "lastName" = '<new_last_name>'
WHERE "authorID" = <author_id>;

-- Delete an author only after removing article_author associations.
DELETE FROM author WHERE "authorID" = <author_id>;


-- ============================================================
-- 4. ARTICLE_AUTHOR
-- Junction table: articleID + authorID form the composite primary key.
-- ============================================================
-- Associate an existing author with an existing article.
INSERT INTO article_author ("articleID", "authorID")
VALUES (<article_id>, <author_id>);

-- View all associations / view authors for one article.
SELECT * FROM article_author;
SELECT aa."articleID", a."authorID", a."firstName", a."lastName"
FROM article_author AS aa
JOIN author AS a ON aa."authorID" = a."authorID"
WHERE aa."articleID" = <article_id>;

-- Change the author association.
UPDATE article_author
SET "authorID" = <new_author_id>
WHERE "articleID" = <article_id> AND "authorID" = <old_author_id>;

-- Remove one article-author association.
DELETE FROM article_author
WHERE "articleID" = <article_id> AND "authorID" = <author_id>;


-- ============================================================
-- 5. STORY
-- Create the story first with currentRevisionNum NULL.
-- After inserting its revision, update currentRevisionNum.
-- ============================================================
-- Create a story (storyID is generated automatically).
INSERT INTO story ("currentRevisionNum", "dateCreated", "dateModified", status)
VALUES (NULL, '<created_timestamp>', '<modified_timestamp>', '<story_status>');

-- View all stories / find one by ID.
SELECT * FROM story;
SELECT * FROM story WHERE "storyID" = <story_id>;

-- Set or change the current revision. That revision must already exist.
UPDATE story
SET "currentRevisionNum" = <revision_number>,
    "dateModified" = '<modified_timestamp>', status = '<story_status>'
WHERE "storyID" = <story_id>;

-- Change a story's status.
UPDATE story
SET status = '<new_status>', "dateModified" = '<modified_timestamp>'
WHERE "storyID" = <story_id>;

-- Delete only after removing dependent revisions and tag associations.
DELETE FROM story WHERE "storyID" = <story_id>;


-- ============================================================
-- 6. STORY_REVISION
-- Composite primary key: (storyID, revisionNum).
-- ============================================================
-- Add a revision to an existing story.
INSERT INTO story_revision ("storyID", "revisionNum", "dateCreated",
                            headline, summary, "changeNote")
VALUES (<story_id>, <revision_number>, '<revision_created_timestamp>',
        '<neutralized_headline>', '<generated_summary>', '<change_note>');

-- View all revisions / all revisions for a story / one specific revision.
SELECT * FROM story_revision;
SELECT * FROM story_revision WHERE "storyID" = <story_id> ORDER BY "revisionNum";
SELECT * FROM story_revision
WHERE "storyID" = <story_id> AND "revisionNum" = <revision_number>;

-- Update a specific revision.
UPDATE story_revision
SET headline = '<new_headline>', summary = '<new_summary>', "changeNote" = '<new_change_note>'
WHERE "storyID" = <story_id> AND "revisionNum" = <revision_number>;

-- Delete only after removing revision_article links and ensuring story
-- does not currently point to this revision.
DELETE FROM story_revision
WHERE "storyID" = <story_id> AND "revisionNum" = <revision_number>;


-- ============================================================
-- 7. REVISION_ARTICLE
-- Composite primary key: (articleID, storyID, revisionNum).
-- ============================================================
-- Link an existing article to an existing story revision.
INSERT INTO revision_article ("articleID", "storyID", "revisionNum", "articleHash")
VALUES (<article_id>, <story_id>, <revision_number>, '<64_character_article_hash>');

-- View all links / sources used for one story revision.
SELECT * FROM revision_article;
SELECT ra."articleID", a.title, a.link, ra."articleHash"
FROM revision_article AS ra
JOIN article AS a ON ra."articleID" = a."articleID"
WHERE ra."storyID" = <story_id> AND ra."revisionNum" = <revision_number>;

-- Update the saved article hash for one association.
UPDATE revision_article
SET "articleHash" = '<new_64_character_article_hash>'
WHERE "articleID" = <article_id> AND "storyID" = <story_id>
  AND "revisionNum" = <revision_number>;

-- Remove an article from one specific revision.
DELETE FROM revision_article
WHERE "articleID" = <article_id> AND "storyID" = <story_id>
  AND "revisionNum" = <revision_number>;


-- ============================================================
-- 8. TAG
-- ============================================================
-- Add a tag (tagID is generated automatically).
INSERT INTO tag (name, description)
VALUES ('<tag_name>', '<tag_description>');

-- View all tags / find one by ID.
SELECT * FROM tag;
SELECT * FROM tag WHERE "tagID" = <tag_id>;

-- Update a tag.
UPDATE tag
SET name = '<new_tag_name>', description = '<new_tag_description>'
WHERE "tagID" = <tag_id>;

-- Delete only after removing story_tag and article_tag associations.
DELETE FROM tag WHERE "tagID" = <tag_id>;


-- ============================================================
-- 9. STORY_TAG
-- Junction table: (storyID, tagID) is the composite primary key.
-- ============================================================
-- Assign an existing tag to an existing story.
INSERT INTO story_tag ("storyID", "tagID")
VALUES (<story_id>, <tag_id>);

-- View all associations / tags assigned to one story.
SELECT * FROM story_tag;
SELECT st."storyID", t."tagID", t.name, t.description
FROM story_tag AS st
JOIN tag AS t ON st."tagID" = t."tagID"
WHERE st."storyID" = <story_id>;

-- Change the tag assigned to a story.
UPDATE story_tag
SET "tagID" = <new_tag_id>
WHERE "storyID" = <story_id> AND "tagID" = <old_tag_id>;

-- Remove one tag from a story.
DELETE FROM story_tag
WHERE "storyID" = <story_id> AND "tagID" = <tag_id>;


-- ============================================================
-- 10. ARTICLE_TAG
-- Junction table: (articleID, tagID) is the composite primary key.
-- ============================================================
-- Assign an existing tag to an existing article.
INSERT INTO article_tag ("articleID", "tagID")
VALUES (<article_id>, <tag_id>);

-- View all associations / tags assigned to one article.
SELECT * FROM article_tag;
SELECT at."articleID", t."tagID", t.name, t.description
FROM article_tag AS at
JOIN tag AS t ON at."tagID" = t."tagID"
WHERE at."articleID" = <article_id>;

-- Change the tag assigned to an article.
UPDATE article_tag
SET "tagID" = <new_tag_id>
WHERE "articleID" = <article_id> AND "tagID" = <old_tag_id>;

-- Remove one tag from an article.
DELETE FROM article_tag
WHERE "articleID" = <article_id> AND "tagID" = <tag_id>;


-- ============================================================
-- GENERAL DATABASE COMMANDS
-- ============================================================

-- List tables in the public schema.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- View columns and data types for a table. Replace <table_name>.
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = '<table_name>'
ORDER BY ordinal_position;

-- Count records in a table. Replace <table_name>.
SELECT COUNT(*) FROM <table_name>;

-- View stories with their current revision headline and summary.
SELECT s."storyID", s.status, s."currentRevisionNum", sr.headline, sr.summary
FROM story AS s
LEFT JOIN story_revision AS sr
  ON sr."storyID" = s."storyID"
 AND sr."revisionNum" = s."currentRevisionNum";

-- View articles with publisher names.
SELECT a."articleID", a.title, a.link, p.name AS publisher_name
FROM article AS a
JOIN publisher AS p ON a."publisherID" = p."publisherID";

-- View articles with their publisher and any associated authors.
SELECT a."articleID", a.title, p.name AS publisher_name,
       au."firstName", au."lastName"
FROM article AS a
JOIN publisher AS p ON a."publisherID" = p."publisherID"
LEFT JOIN article_author AS aa ON a."articleID" = aa."articleID"
LEFT JOIN author AS au ON aa."authorID" = au."authorID";


-- ============================================================
-- SAFE TESTING AND DELETION
-- ============================================================

-- Start a transaction before testing changes.
BEGIN;

-- Run the INSERT, UPDATE, or DELETE command(s) you want to test here.

-- Keep the changes:
-- COMMIT;

-- Undo the changes made since BEGIN:
-- ROLLBACK;

-- WARNING: DELETE removes rows matching its WHERE condition.
-- Without WHERE, DELETE removes every row in the table.
-- TRUNCATE removes every row from a table and may be blocked by
-- foreign-key references. Avoid CASCADE unless intended, because it deletes all instances.
-- Template only:
-- TRUNCATE TABLE <table_name>;
