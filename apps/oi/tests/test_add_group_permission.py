# -*- coding: utf-8 -*-
"""Tests of who may open the form to add a group."""

import pytest

from django.conf import settings
from django.contrib.auth.models import Permission
from django.urls import reverse


@pytest.mark.django_db
def test_visitor_is_sent_to_login(client):
    """A visitor who is not logged in is sent to the login page."""
    response = client.get(reverse('add_group'))

    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)


@pytest.mark.django_db
def test_user_who_may_not_add_is_sent_to_login(client, any_indexer):
    """A user without the permission to reserve gets no form."""
    client.force_login(any_indexer)

    response = client.get(reverse('add_group'))

    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)


@pytest.mark.django_db
def test_user_who_may_add_gets_the_form(client, any_indexer):
    """A user with the permission to reserve gets the form."""
    any_indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(any_indexer)

    response = client.get(reverse('add_group'))

    assert response.status_code == 200
    assert response.context['object_name'] == 'Group'
