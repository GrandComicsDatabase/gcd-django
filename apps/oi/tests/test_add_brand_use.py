# -*- coding: utf-8 -*-
"""Tests of the form to add a brand use, through the real view."""

import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.oi import states
from apps.oi.models import Changeset, CTYPES


@pytest.fixture
def add_url(client, any_indexer, any_added_brand, any_added_publisher):
    """Log in an indexer who may add and return the URL of the form."""
    any_indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(any_indexer)
    return reverse('add_brand_use',
                   kwargs={'brand_id': any_added_brand.id,
                           'publisher_id': any_added_publisher.id})


@pytest.mark.django_db
@pytest.mark.parametrize('years, error', [
  ({'year_began': '1980', 'year_ended': '1970'},
   'Year ended cannot be before year began.'),
  ({'year_began': 'unknown', 'year_ended': ''},
   'Enter a whole number.'),
])
def test_invalid_form_is_shown_again(client, add_url, years, error):
    response = client.post(add_url, {'notes': '', 'comments': '', **years})

    assert response.status_code == 200
    assert error in response.content.decode()
    assert not Changeset.objects.filter(
      change_type=CTYPES['brand_use']).exists()


@pytest.mark.django_db
def test_valid_form_is_submitted(client, add_url):
    response = client.post(add_url, {'year_began': '1970',
                                     'year_ended': '1975',
                                     'notes': '',
                                     'comments': 'Seen on the covers.'})

    assert response.status_code == 302
    changeset = Changeset.objects.get(change_type=CTYPES['brand_use'])
    assert changeset.state == states.PENDING
    assert changeset.branduserevisions.get().year_began == 1970
