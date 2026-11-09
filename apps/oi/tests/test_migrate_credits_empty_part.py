"""A migration of text credits with an empty part between semicolons."""
import pytest


@pytest.fixture
def issue_revision(any_edit_story_rev):
    """Return the issue revision that goes with the sequence revision."""
    return any_edit_story_rev.changeset.issuerevisions.get()


@pytest.mark.django_db
@pytest.mark.parametrize('text,expected', [
    ('Nobody One;;Nobody Two', 'Nobody One; Nobody Two'),
    ('Nobody One; ;Nobody Two', 'Nobody One; Nobody Two'),
    (' ;Nobody One', 'Nobody One'),
    (';', ''),
])
def test_empty_part_of_a_story_credit_is_skipped(any_edit_story_rev, text,
                                                 expected):
    """An empty part must not stop the migration of a sequence."""
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    assert any_edit_story_rev.script == expected


@pytest.mark.django_db
@pytest.mark.parametrize('text,expected', [
    ('Nobody One;;Nobody Two', 'Nobody One; Nobody Two'),
    (' ;Nobody One', 'Nobody One'),
    (';', ''),
])
def test_empty_part_of_an_issue_editing_credit_is_skipped(issue_revision, text,
                                                          expected):
    """An empty part must not stop the migration of an issue."""
    issue_revision.editing = text

    issue_revision.migrate_credits()

    assert issue_revision.editing == expected
