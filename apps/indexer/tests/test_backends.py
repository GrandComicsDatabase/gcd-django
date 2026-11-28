# -*- coding: utf-8 -*-
"""Tests of the session of an account, by the way it logged in."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.stddata.models import Country

pytestmark = pytest.mark.django_db

# The login with the e-mail address, then the one with the username.
BACKENDS = ['apps.indexer.backends.EmailBackend',
            'django.contrib.auth.backends.ModelBackend']


@pytest.fixture
def member():
    """
    A user with an indexer profile.
    """
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    user = User.objects.create_user('a_member', email='member@example.com')
    Indexer.objects.create(user=user, country=country)
    return user


def _profile(client, user):
    """
    Open the profile page of the user, which asks for a login.
    """
    return client.get(reverse('view_profile', kwargs={'user_id': user.id}))


@pytest.mark.parametrize('backend', BACKENDS)
def test_active_member_stays_logged_in(client, member, backend):
    client.force_login(member, backend=backend)

    response = _profile(client, member)

    assert response.status_code == 200


@pytest.mark.parametrize('backend', BACKENDS)
def test_deactivated_member_is_logged_out(client, member, backend):
    client.force_login(member, backend=backend)
    member.is_active = False
    member.save()

    response = _profile(client, member)

    assert response.status_code == 302
    assert response.url == reverse('login')
