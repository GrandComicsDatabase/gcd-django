# -*- coding: utf-8 -*-
"""Tests of the dates of the dump files on the download page."""

import calendar
import os
import warnings
from datetime import datetime

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.stddata.models import Country

# The modification time given to the MySQL dump, in UTC.
DUMP_TIME = datetime(2020, 1, 2, 3, 4, 5)


@pytest.fixture
def member(db):
    """A user with an indexer profile."""
    country = Country.objects.get_or_create(
        code='XZY', defaults={'name': 'Test Country'})[0]
    user = User.objects.create_user('a_member', email='member@example.com')
    Indexer.objects.create(user=user, country=country)
    return user


@pytest.fixture
def mysql_dump(settings, tmp_path):
    """Only the MySQL dump is there, last changed at DUMP_TIME."""
    settings.MEDIA_ROOT = str(tmp_path)
    dump = tmp_path / settings.DUMP_DIR / settings.MYSQL_DUMP
    dump.parent.mkdir()
    dump.write_bytes(b'')
    seconds = calendar.timegm(DUMP_TIME.timetuple())
    os.utime(dump, (seconds, seconds))


def test_dump_dates_in_utc(client, member, mysql_dump):
    """The page gives each dump's UTC date, without a deprecated call."""
    client.force_login(member)
    with warnings.catch_warnings():
        warnings.filterwarnings('error', message='.*utcfromtimestamp',
                                category=DeprecationWarning)
        response = client.get(reverse('stats:download'))

    assert response.status_code == 200
    timestamps = dict(response.context['timestamps'])
    assert timestamps == {'MySQL': DUMP_TIME, 'Name-Value': 'never',
                          'SQLite': 'never'}
    assert timestamps['MySQL'].tzinfo is None
