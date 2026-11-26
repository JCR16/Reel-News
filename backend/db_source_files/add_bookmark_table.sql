-- Creates the relationship between authenticated users
-- and their bookmarked stories.
--
-- Prerequisites:
-- The auth_user and story tables must already exist.

CREATE TABLE IF NOT EXISTS bookmark (
    "userID" INTEGER NOT NULL,
    "storyID" INTEGER NOT NULL,
    "dateCreated" TIMESTAMP WITH TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY ("userID", "storyID"),

    FOREIGN KEY ("userID")
        REFERENCES auth_user (id)
        ON DELETE CASCADE,

    FOREIGN KEY ("storyID")
        REFERENCES story ("storyID")
        ON DELETE CASCADE
);

-- Improve performance when looking up bookmarks by story.
CREATE INDEX IF NOT EXISTS idx_bookmark_story
    ON bookmark ("storyID");