"""What a migration of text credits leaves behind."""
import pytest

from apps.gcd.models import CreditType
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi import states
from apps.oi.models import (Changeset, CreatorNameDetailRevision,
                            CreatorRevision, CTYPES)
from apps.stddata.models import Date, Script


def _creator(name, indexer):
    """Create a creator with its official name through approved revisions."""
    script, _ = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    changeset = Changeset.objects.create(indexer=indexer,
                                         state=states.APPROVED,
                                         change_type=CTYPES['creator'])
    revision = CreatorRevision.objects.create(
      changeset=changeset, gcd_official_name=name,
      birth_date=Date.objects.create(), death_date=Date.objects.create())
    CreatorNameDetailRevision.objects.create(
      changeset=changeset, creator_revision=revision, name=name,
      sort_name=name, is_official_name=True, in_script=script)
    revision.commit_to_display()
    changeset.creatornamedetailrevisions.get().commit_to_display()
    return revision.creator


@pytest.fixture
def credit_types():
    """Make sure every credit type a migration can use exists."""
    for name, pk in CREDIT_TYPES.items():
        CreditType.objects.get_or_create(
          id=pk, defaults={'name': name, 'sort_code': pk})


@pytest.fixture
def issue_revision(any_edit_story_rev):
    """Return the issue revision that goes with the sequence revision."""
    return any_edit_story_rev.changeset.issuerevisions.get()


@pytest.mark.django_db
@pytest.mark.parametrize('text', [
    'Nobody Known (painting) ?',
    'Nobody Known (painting)?',
    'Nobody Known (credited) ?',
    'Nobody Known ? (painting)',
    'Nobody Known ?',
    'Nobody One (painting) ?; Nobody Two',
])
def test_story_credit_not_migrated_stays_as_it_was(any_edit_story_rev, text):
    """A credit without a matching creator keeps its exact text."""
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    assert any_edit_story_rev.script == text


@pytest.mark.django_db
@pytest.mark.parametrize('text', [
    'Nobody Known (consulting) ?',
    'Nobody Known (consulting)?',
    'Nobody Known ?',
])
def test_issue_editing_not_migrated_stays_as_it_was(issue_revision, text):
    """An editing credit without a matching creator keeps its exact text."""
    issue_revision.editing = text

    issue_revision.migrate_credits()

    assert issue_revision.editing == text


@pytest.mark.django_db
def test_note_of_a_migrated_story_credit_has_no_question_mark(
  any_edit_story_rev, any_indexer, credit_types):
    """The note of a migrated credit does not take the question mark."""
    _creator('Some Artist', any_indexer)
    any_edit_story_rev.script = 'Some Artist (painting) ?'

    any_edit_story_rev.migrate_credits()

    credit = any_edit_story_rev.story_credit_revisions.get()
    assert credit.credit_name == 'painting'
    assert credit.uncertain
    assert any_edit_story_rev.script == ''


@pytest.mark.django_db
def test_note_of_a_migrated_issue_credit_has_no_question_mark(
  issue_revision, any_indexer, credit_types):
    """The note of a migrated issue credit does not take the mark."""
    _creator('Some Editor', any_indexer)
    issue_revision.editing = 'Some Editor (consulting) ?'

    issue_revision.migrate_credits()

    credit = issue_revision.issue_credit_revisions.get()
    assert credit.credit_name == 'consulting'
    assert credit.uncertain
    assert issue_revision.editing == ''
