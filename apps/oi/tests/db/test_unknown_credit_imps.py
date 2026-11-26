"""IMPs for a question mark in a credit field of a sequence."""

import pytest
from django.test import RequestFactory

from apps.gcd.models import (
    CREDIT_TYPES, Creator, CreatorNameDetail, CreditType, StoryCredit)
from apps.oi.forms.story import (
    StoryCharacterRevisionFormSet, StoryGroupRevisionFormSet,
    StoryRevisionFormSet)
from apps.oi.models import StoryCreditRevision
from apps.stddata.models import Script

COMBINED_CREDIT_TYPES = {
    7: 'pencils and inks',
    9: 'painting',
    13: 'script, pencils, inks, colors, and letters',
}


def _creator_name():
    """Return the official name of a new test creator."""
    creator = Creator.objects.create(
      gcd_official_name='Test Creator', birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='')
    script = Script.objects.create(code='Tst', number=999,
                                   name='Test Script')
    return CreatorNameDetail.objects.create(
      name='Test Creator', creator=creator, is_official_name=True,
      in_script=script)


def _credit_type(credit_type_id, name):
    """Return the credit type with the id, made if the test DB lacks it."""
    return CreditType.objects.get_or_create(
      id=credit_type_id,
      defaults={'name': name, 'sort_code': credit_type_id})[0]


def _add_credit(story_revision, credit_type_name):
    """Add a structured credit of the given type to the story revision."""
    StoryCreditRevision.objects.create(
      changeset=story_revision.changeset, story_revision=story_revision,
      creator=_creator_name(),
      credit_type=_credit_type(CREDIT_TYPES[credit_type_name],
                               credit_type_name))


def _keep_credit(story_revision, credit_type_name):
    """Give the edited story an empty text field and a structured credit.

    Return the credit revision of the edit, unchanged.
    """
    previous = story_revision.previous()
    setattr(previous, credit_type_name, '')
    previous.save()
    creator_name = _creator_name()
    credit_type = _credit_type(CREDIT_TYPES[credit_type_name],
                               credit_type_name)
    credit = StoryCredit.objects.create(
      story=story_revision.story, creator=creator_name,
      credit_type=credit_type, signed_as='', credited_as='', sourced_by='',
      credit_name='')
    StoryCreditRevision.objects.create(
      changeset=previous.changeset, story_revision=previous,
      story_credit=credit, creator=creator_name, credit_type=credit_type,
      committed=True)
    return StoryCreditRevision.clone(credit, story_revision.changeset,
                                     story_revision=story_revision)


def _save_credit_form(story_revision, credit_type_id):
    """Save a credit of the type as the Creator Credits tab does."""
    for name in ('script', 'pencils', 'inks', 'colors', 'letters'):
        _credit_type(CREDIT_TYPES[name], name)
    _credit_type(credit_type_id, COMBINED_CREDIT_TYPES[credit_type_id])
    data = {}
    for formset in (StoryRevisionFormSet, StoryCharacterRevisionFormSet,
                    StoryGroupRevisionFormSet):
        prefix = formset.get_default_prefix()
        data[prefix + '-TOTAL_FORMS'] = '0'
        data[prefix + '-INITIAL_FORMS'] = '0'
    prefix = StoryRevisionFormSet.get_default_prefix()
    data[prefix + '-TOTAL_FORMS'] = '1'
    data[prefix + '-0-creator'] = str(_creator_name().id)
    data[prefix + '-0-credit_type'] = str(credit_type_id)
    request = RequestFactory().post('/', data)
    story_revision.process_extra_forms(story_revision.extra_forms(request))


def _imps_with(story_revision, field, value):
    """Return the IMPs of the story revision with the field set to value."""
    setattr(story_revision, field, value)
    story_revision.save()
    return story_revision.calculate_imps()


@pytest.mark.django_db
@pytest.mark.parametrize('field, credit_type', [('script', 'pencils'),
                                                ('letters', 'script')])
def test_question_mark_next_to_other_credit_type_does_not_score(
        any_added_story_rev, field, credit_type):
    """A "?" earns nothing next to a structured credit of another type."""
    rev = any_added_story_rev
    _add_credit(rev, credit_type)

    assert _imps_with(rev, field, '?') == _imps_with(rev, field, '')


@pytest.mark.django_db
def test_question_mark_next_to_same_credit_type_scores(any_added_story_rev):
    """A "?" next to a structured credit of its type scores like a name."""
    rev = any_added_story_rev
    _add_credit(rev, 'script')

    assert _imps_with(rev, 'script', '?') == \
        _imps_with(rev, 'script', 'Some Writer')


@pytest.mark.django_db
@pytest.mark.parametrize('credit_changed', [False, True])
def test_question_mark_on_edit_adds_nothing_to_the_credit(
        any_edit_story_rev, credit_changed):
    """On an edit only a changed credit of its type gives a "?" an IMP."""
    rev = any_edit_story_rev
    credit_revision = _keep_credit(rev, 'script')
    if credit_changed:
        credit_revision.uncertain = True
        credit_revision.save()

    assert _imps_with(rev, 'script', '?') == _imps_with(rev, 'script', '')


@pytest.mark.django_db
def test_question_mark_next_to_credit_retyped_away_scores(
        any_edit_story_rev):
    """A credit retyped to another type is a change of its old type."""
    rev = any_edit_story_rev
    credit_revision = _keep_credit(rev, 'script')
    credit_revision.credit_type = _credit_type(CREDIT_TYPES['pencils'],
                                               'pencils')
    credit_revision.save()

    assert _imps_with(rev, 'script', '?') == _imps_with(rev, 'script', '')


@pytest.mark.django_db
@pytest.mark.parametrize('credit_type_id, field', [(7, 'inks'),
                                                   (9, 'pencils'),
                                                   (13, 'letters')])
def test_question_mark_next_to_combined_credit_type_scores(
        any_added_story_rev, credit_type_id, field):
    """A combined credit type is saved as one credit of each of its types."""
    rev = any_added_story_rev
    _save_credit_form(rev, credit_type_id)

    assert not rev.story_credit_revisions.filter(
      credit_type_id=credit_type_id).exists()
    assert _imps_with(rev, field, '?') == \
        _imps_with(rev, field, 'Some Artist')
