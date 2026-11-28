"""Changes of a sequence edit when the previous change deleted a credit."""

import pytest

from apps.gcd.models import (
    CREDIT_TYPES, Creator, CreatorNameDetail, CreditType)
from apps.oi.models import StoryCreditRevision
from apps.stddata.models import Script


def _add_credit(story_revision, credit_type_name, deleted):
    """Add a creator credit of the given type to the story revision."""
    creator = Creator.objects.get_or_create(
      gcd_official_name='Test Creator', birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='')[0]
    script = Script.objects.get_or_create(code='Tst', number=999,
                                          name='Test Script')[0]
    creator_name = CreatorNameDetail.objects.get_or_create(
      name='Test Creator', creator=creator, is_official_name=True,
      in_script=script)[0]
    credit_type = CreditType.objects.get_or_create(
      id=CREDIT_TYPES[credit_type_name],
      defaults={'name': credit_type_name,
                'sort_code': CREDIT_TYPES[credit_type_name]})[0]
    StoryCreditRevision.objects.create(
      changeset=story_revision.changeset, story_revision=story_revision,
      creator=creator_name, credit_type=credit_type, deleted=deleted)


@pytest.mark.django_db
@pytest.mark.parametrize('credit_type', ['script', 'pencils'])
def test_credit_deleted_by_previous_change_is_no_change(any_edit_story_rev,
                                                        credit_type):
    """A creator credit the previous change deleted changes nothing now."""
    rev = any_edit_story_rev
    _add_credit(rev.previous(), credit_type, deleted=True)

    rev.compare_changes()
    assert rev.changed[credit_type] is False
    assert rev.is_changed is False


@pytest.mark.django_db
def test_credit_deleted_by_previous_change_earns_no_imp(any_edit_story_rev):
    """An edit that changes nothing earns no IMP for such a credit."""
    rev = any_edit_story_rev
    _add_credit(rev.previous(), 'script', deleted=True)

    assert rev.calculate_imps() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('in_edit', ['deleted', 'missing'])
def test_credit_kept_by_previous_change_and_gone_now_is_a_change(
        any_edit_story_rev, in_edit):
    """A creator credit the previous change kept and the edit lacks counts."""
    rev = any_edit_story_rev
    _add_credit(rev.previous(), 'script', deleted=False)
    if in_edit == 'deleted':
        _add_credit(rev, 'script', deleted=True)

    rev.compare_changes()
    assert rev.changed['script'] is True
    assert rev.calculate_imps() == 1
