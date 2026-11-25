"""Tests of the order of the birth and death dates of a creator."""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.oi.forms.creator import get_creator_revision_form

ERROR = 'Death date cannot be before birth date.'


def _form(birth, death):
    """Return the creator form with the dates as its page sends them."""
    return get_creator_revision_form()({'birth_date-date': birth,
                                        'death_date-date': death})


@pytest.mark.django_db
@pytest.mark.parametrize(('birth', 'death'), (
    ('1950', '1949'),
    ('1950-05', '1950-04'),
    ('1950-05-10', '1950-05-09'),
    ('1950-05-10', '1949-12-31'),
))
def test_death_date_before_birth_date_is_refused(birth, death):
    """A death date before the birth date is an error of the form."""
    form = _form(birth, death)

    assert not form.is_valid()
    assert form.errors == {'__all__': [ERROR]}


@pytest.mark.django_db
@pytest.mark.parametrize(('birth', 'death'), (
    ('', ''),
    ('1950', ''),
    ('', '1949'),
    ('1950', '1950'),
    ('1950-05-10', '1951-01-01'),
    ('1950-05', '1950'),
    ('1950-05-10', '1950-05'),
    ('1950?', '1949'),
    ('195?', '1949'),
    ('1950', '1949?'),
    ('1950-05?', '1950-04'),
    ('1950-05-10', '1950-05-?'),
))
def test_death_date_not_known_to_be_before_passes(birth, death):
    """Only the parts that both dates have, and as certain, compare."""
    form = _form(birth, death)

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_add_creator_page_shows_the_error(client, any_indexer):
    """The page to add a creator shows the error to the indexer."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)

    response = client.post(reverse('add_creator'),
                           {'birth_date-date': '1950',
                            'death_date-date': '1949'})

    assert response.status_code == 200
    assert ERROR in response.content.decode()
