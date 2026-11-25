"""IMPs for a question mark in a credit field of a sequence."""

import pytest

from apps.gcd.models import (
    CREDIT_TYPES, Creator, CreatorNameDetail, CreditType)
from apps.oi.models import StoryCreditRevision
from apps.stddata.models import Script


def _add_credit(story_revision, credit_type_name):
    """Add a structured credit of the given type to the story revision."""
    creator = Creator.objects.create(
      gcd_official_name='Test Creator', birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='')
    script = Script.objects.create(code='Tst', number=999,
                                   name='Test Script')
    creator_name = CreatorNameDetail.objects.create(
      name='Test Creator', creator=creator, is_official_name=True,
      in_script=script)
    credit_type = CreditType.objects.get_or_create(
      id=CREDIT_TYPES[credit_type_name],
      defaults={'name': credit_type_name,
                'sort_code': CREDIT_TYPES[credit_type_name]})[0]
    StoryCreditRevision.objects.create(
      changeset=story_revision.changeset, story_revision=story_revision,
      creator=creator_name, credit_type=credit_type)


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
