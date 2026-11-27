# Testing

## Overview

Reel News uses Django's testing framework to verify story management, editorial workflows, bookmarking, and story views.

The unit tests use mocked database queries and external services, allowing them to run without connecting to PostgreSQL or making Gemini API requests.

## Running Tests

Activate the virtual environment and run the following commands from the `app` directory.

Run all tests:

```bash
python manage.py test --verbosity 2
```

Run tests for a specific application:

```bash
python manage.py test stories --verbosity 2
python manage.py test accounts --verbosity 2
```

Run a specific test file:

```bash
python manage.py test stories.tests.test_story_manager --verbosity 2
```

Run a specific test class:

```bash
python manage.py test stories.tests.test_story_manager.StoryCreationTests --verbosity 2
```

Run a specific test method:

```bash
python manage.py test stories.tests.test_story_manager.StoryCreationTests.test_create_story --verbosity 2
```

## Test Organization

```text
app/
├── accounts/
│   └── tests/
│       ├── test_bookmark_manager.py
│       └── test_bookmark_views.py
├── stories/
│   └── tests/
│       ├── test_article_cleanup.py
│       ├── test_story_archiving.py
│       ├── test_story_deletion.py
│       ├── test_story_manager.py
│       ├── test_story_publication.py
│       └── test_views.py
└── config/
    └── test_runner.py
```

| Test File | Coverage |
|---|---|
| `test_bookmark_manager.py` | Bookmark creation, removal, status, and retrieval |
| `test_bookmark_views.py` | Bookmark endpoints, authentication, HTTP methods, and URL routing |
| `test_article_cleanup.py` | Identification and removal of unused article text |
| `test_story_archiving.py` | Story archiving and restoration |
| `test_story_deletion.py` | Deletion eligibility, related records, and orphaned articles |
| `test_story_manager.py` | Story creation, revision generation, article linking, and regeneration |
| `test_story_publication.py` | Revision approval, rejection, and review feedback |
| `test_views.py` | Story feed, detail pages, bookmark states, and URL routing |

## Testing Approach

- `SimpleTestCase` prevents unit tests from accessing the database.
- `MagicMock` and `patch` simulate database operations and external services.
- `RequestFactory` constructs HTTP requests for testing views without running middleware.
- `subTest()` tests multiple scenarios within a single test method.
- `__wrapped__` allows transaction-decorated service functions to be tested without opening database transactions.

Tests cover successful operations, invalid inputs, missing records, and error handling.

## Custom Test Runner

The custom test runner is located in `config/test_runner.py` and configured through Django's settings.

It groups tests into readable sections, displays individual test and subtest results, and provides a summary after execution.

Example output:

```text
Test Results Summary
--------------------
Test methods executed: 162
Passed: 162
Failure reports: 0
Error reports: 0
Skipped: 0

Subtests passed: 74
Subtests failed or errored: 0
```

Subtests are reported separately because a single test method may cover multiple scenarios.

## Adding New Tests

- Place tests in the appropriate application's `tests/` directory.
- Use descriptive class and method names.
- Include short docstrings describing the purpose of each test.
- Mock dependencies where they are referenced by the code being tested.
- Test both successful operations and failure conditions.
- Run the full test suite before submitting a pull request.

Update affected tests when modifying existing functionality, and add regression tests when fixing bugs.

## Current Limitations

The current test suite focuses on isolated unit testing. It does not verify:

- Actual PostgreSQL queries, constraints, or persistence
- Transaction rollback and concurrent database operations
- Live Gemini API responses
- Middleware, CSRF enforcement, or session persistence
- Browser interactions and frontend rendering

Integration and end-to-end testing should be performed separately from the unit test suite.