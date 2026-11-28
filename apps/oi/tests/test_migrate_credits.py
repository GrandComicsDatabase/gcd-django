"""What a migration of text credits leaves behind."""
import pytest

from apps.gcd.models import CreditType
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi import states
from apps.oi.models import (Changeset, CreatorNameDetailRevision,
                            CreatorRevision, CTYPES)
from apps.stddata.models import Date, Script


def _creator(name, indexer, disambiguation=''):
    """Create a creator with its official name through approved revisions."""
    script, _ = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    changeset = Changeset.objects.create(indexer=indexer,
                                         state=states.APPROVED,
                                         change_type=CTYPES['creator'])
    revision = CreatorRevision.objects.create(
      changeset=changeset, gcd_official_name=name,
      disambiguation=disambiguation,
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
@pytest.mark.parametrize('text,signed_as,credit_name,uncertain', [
    ('Some Artist (signed as S. A.)', 'S. A.', '', False),
    ('Some Artist (signed as S. A.) (painting)', 'S. A.', 'painting', False),
    ('Some Artist ? (signed as S. A.) (painting)', 'S. A.', 'painting', True),
    ('Some Artist (signed as S. A.) ?', 'S. A.', '', True),
])
def test_story_credit_written_as_signed_as_is_migrated(
  any_edit_story_rev, any_indexer, credit_types, text, signed_as,
  credit_name, uncertain):
    """A sequence credit in the form the site shows keeps its signature."""
    _creator('Some Artist', any_indexer)
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    credit = any_edit_story_rev.story_credit_revisions.get()
    assert credit.is_signed
    assert credit.signed_as == signed_as
    assert not credit.is_credited
    assert credit.credit_name == credit_name
    assert credit.uncertain == uncertain
    assert any_edit_story_rev.script == ''


@pytest.mark.django_db
@pytest.mark.parametrize('text,name,is_signed,credit_name', [
    ('Some Artist (signed)', 'Some Artist', True, ''),
    ('Some Artist (signed) (painting)', 'Some Artist', True, 'painting'),
    ('Some Artist (signed as Some (Smiling) Artist)', 'Some Artist', False,
     'signed as Some (Smiling) Artist'),
    ('Some Artist (signed as S. A.', 'Some Artist', False,
     '(signed as S. A.'),
    ('Some Artist [as S. Artiste] (signed as S. A.)', 'S. Artiste', False,
     'signed as S. A.'),
])
def test_story_signature_note_is_migrated_as_before(
  any_edit_story_rev, any_indexer, credit_types, text, name, is_signed,
  credit_name):
    """The other signature notes of a sequence credit migrate as they did."""
    _creator('Some Artist', any_indexer)
    _creator('S. Artiste', any_indexer)
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    credit = any_edit_story_rev.story_credit_revisions.get()
    assert credit.creator.name == name
    assert credit.is_signed == is_signed
    assert credit.signed_as == ''
    assert credit.credit_name == credit_name


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


@pytest.mark.django_db
@pytest.mark.parametrize('text,credited_as,credit_name,uncertain', [
    ('Some Editor (credited as Some Other Editor) '
     '(a cura di, senior art designer);',
     'Some Other Editor', 'a cura di, senior art designer', False),
    ('Some Editor (credited as Some Other Editor)',
     'Some Other Editor', 'editor', False),
    ('Some Editor (credited as Some Other Editor) (a cura di) ?',
     'Some Other Editor', 'a cura di', True),
    ('Some Editor (credited as Some Editor) (a cura di)',
     '', 'a cura di', False),
])
def test_issue_credit_written_as_credited_as_is_migrated(
  issue_revision, any_indexer, credit_types, text, credited_as, credit_name,
  uncertain):
    """An editing credit in the form the site shows keeps its parts."""
    _creator('Some Editor', any_indexer)
    issue_revision.editing = text

    issue_revision.migrate_credits()

    credit = issue_revision.issue_credit_revisions.get()
    assert credit.is_credited
    assert credit.credited_as == credited_as
    assert credit.credit_name == credit_name
    assert credit.uncertain == uncertain
    assert issue_revision.editing == ''


@pytest.mark.django_db
@pytest.mark.parametrize('text,credited_as,credit_name,uncertain', [
    ('Some Artist (credited as S. Artiste) (painting)',
     'S. Artiste', 'painting', False),
    ('Some Artist (credited as S. Artiste)', 'S. Artiste', '', False),
    ('Some Artist ? (credited as S. Artiste) (painting)',
     'S. Artiste', 'painting', True),
    ('Some Artist (credited as S. Artiste) (painting) ?',
     'S. Artiste', 'painting', True),
    ('Some Artist (credited as Some Artist)', '', '', False),
])
def test_story_credit_written_as_credited_as_is_migrated(
  any_edit_story_rev, any_indexer, credit_types, text, credited_as,
  credit_name, uncertain):
    """A sequence credit in the form the site shows keeps its parts."""
    _creator('Some Artist', any_indexer)
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    credit = any_edit_story_rev.story_credit_revisions.get()
    assert credit.is_credited
    assert credit.credited_as == credited_as
    assert credit.credit_name == credit_name
    assert credit.uncertain == uncertain
    assert any_edit_story_rev.script == ''


@pytest.mark.django_db
@pytest.mark.parametrize('text,is_credited,credit_name', [
    ('Some Editor (credited)', True, 'editor'),
    ('Some Editor (credited) (managing editor)', True, 'managing editor'),
    ('Some Editor (credited) (managing editor, art director)', True,
     'managing editor, art director'),
    ('Some Editor (credited as Some (Smiling) Editor)', False,
     'credited as Some (Smiling) Editor'),
    ('Some Editor (credited as Some Other Editor', False,
     '(credited as Some Other Editor'),
])
def test_issue_credit_note_is_migrated_as_before(
  issue_revision, any_indexer, credit_types, text, is_credited, credit_name):
    """The other notes of an editing credit migrate as they did."""
    _creator('Some Editor', any_indexer)
    issue_revision.editing = text

    issue_revision.migrate_credits()

    credit = issue_revision.issue_credit_revisions.get()
    assert credit.is_credited == is_credited
    assert credit.credited_as == ''
    assert credit.credit_name == credit_name


@pytest.mark.django_db
@pytest.mark.parametrize('text,is_credited,credit_name', [
    ('Some Artist (credited)', True, ''),
    ('Some Artist (credited) (painting)', True, 'painting'),
    ('Some Artist (credited) (plot, script)', True, 'plot, script'),
    ('Some Artist (credited as Some (Smiling) Artist)', False,
     'credited as Some (Smiling) Artist'),
    ('Some Artist (credited as Some Other Artist', False,
     '(credited as Some Other Artist'),
])
def test_story_credit_note_is_migrated_as_before(
  any_edit_story_rev, any_indexer, credit_types, text, is_credited,
  credit_name):
    """The other notes of a sequence credit migrate as they did."""
    _creator('Some Artist', any_indexer)
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    credit = any_edit_story_rev.story_credit_revisions.get()
    assert credit.is_credited == is_credited
    assert credit.credited_as == ''
    assert credit.credit_name == credit_name


@pytest.fixture
def same_name_creators(any_indexer):
    """
    Create five creators named 'Some Editor', with the disambiguations
    'comics editor', 'colorist', twice 'letterer' and none, and one
    creator named 'S. Editeur'.
    """
    for disambiguation in ['comics editor', 'colorist', 'letterer',
                           'letterer', '']:
        _creator('Some Editor', any_indexer, disambiguation)
    _creator('S. Editeur', any_indexer)


@pytest.mark.django_db
@pytest.mark.parametrize(
  'text,disambiguation,credited_as,credit_name,uncertain', [
    ('Some Editor [comics editor]', 'comics editor', '', 'editor', False),
    ('Some Editor [Comics Editor]', 'comics editor', '', 'editor', False),
    ('Some Editor [ comics editor ] (managing editor) ?', 'comics editor',
     '', 'managing editor', True),
    ('Some Editor [colorist] (credited as S. E.)', 'colorist', 'S. E.',
     'editor', False),
  ])
def test_issue_credit_with_a_disambiguation_is_migrated(
  issue_revision, same_name_creators, credit_types, text, disambiguation,
  credited_as, credit_name, uncertain):
    """The bracket picks the creator of the name with that disambiguation."""
    issue_revision.editing = text

    issue_revision.migrate_credits()

    assert issue_revision.editing == ''
    credit = issue_revision.issue_credit_revisions.get()
    assert credit.creator.name == 'Some Editor'
    assert credit.creator.creator.disambiguation == disambiguation
    assert credit.credited_as == credited_as
    assert credit.credit_name == credit_name
    assert credit.uncertain == uncertain


@pytest.mark.django_db
@pytest.mark.parametrize(
  'text,disambiguation,is_signed,credit_name,uncertain', [
    ('Some Editor [comics editor]', 'comics editor', False, '', False),
    ('Some Editor [colorist] (signed)', 'colorist', True, '', False),
    ('Some Editor [Colorist] (painting) ?', 'colorist', False, 'painting',
     True),
  ])
def test_story_credit_with_a_disambiguation_is_migrated(
  any_edit_story_rev, same_name_creators, credit_types, text,
  disambiguation, is_signed, credit_name, uncertain):
    """The bracket picks the creator of the name with that disambiguation."""
    any_edit_story_rev.script = text

    any_edit_story_rev.migrate_credits()

    assert any_edit_story_rev.script == ''
    credit = any_edit_story_rev.story_credit_revisions.get()
    assert credit.creator.name == 'Some Editor'
    assert credit.creator.creator.disambiguation == disambiguation
    assert credit.is_signed == is_signed
    assert credit.signed_as == ''
    assert credit.credit_name == credit_name
    assert credit.uncertain == uncertain


@pytest.mark.django_db
@pytest.mark.parametrize('text', [
    'Some Editor',
    'Some Editor [letterer]',
    'Some Editor [inker]',
    'Some Editor []',
    'Other Editor [colorist]',
])
def test_credit_without_one_disambiguated_name_stays_as_text(
  any_edit_story_rev, issue_revision, same_name_creators, credit_types,
  text):
    """A bracket that picks no creator, or two, leaves the text."""
    any_edit_story_rev.script = text
    issue_revision.editing = text

    any_edit_story_rev.migrate_credits()
    issue_revision.migrate_credits()

    assert any_edit_story_rev.script == text
    assert not any_edit_story_rev.story_credit_revisions.exists()
    assert issue_revision.editing == text
    assert not issue_revision.issue_credit_revisions.exists()


@pytest.mark.django_db
def test_credit_with_as_in_brackets_is_migrated_as_before(
  any_edit_story_rev, issue_revision, same_name_creators, credit_types):
    """A name in [as ...] is still the one credited."""
    any_edit_story_rev.script = 'Some Editor [as S. Editeur]'
    issue_revision.editing = 'Some Editor [as S. Editeur]'

    any_edit_story_rev.migrate_credits()
    issue_revision.migrate_credits()

    story_credit = any_edit_story_rev.story_credit_revisions.get()
    issue_credit = issue_revision.issue_credit_revisions.get()
    assert story_credit.creator.name == 'S. Editeur'
    assert issue_credit.creator.name == 'S. Editeur'
