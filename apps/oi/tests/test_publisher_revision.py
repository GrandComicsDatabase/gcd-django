# -*- coding: utf-8 -*-

import pytest
import mock

from django.contrib.auth.models import User

from apps.gcd.models import Country, Indexer
from apps.oi import states
from apps.oi.models import PublisherRevision, Changeset, CTYPES


KEYWORDS = ['bar', 'foo']
KEYWORD_STRING = '; '.join(KEYWORDS)

PUBLISHER_ADD_VALUES = {
    'name': 'Test Publisher',
    'year_began': 1960,
    'year_ended': None,
    'year_began_uncertain': True,
    'year_ended_uncertain': False,
    'notes': 'publisher add notes',
    'url': 'http://whatever.com',
}


@pytest.fixture
def any_country():
    c = Country.objects.get_or_create(code='XZZ', name='Test Country')
    return c[0]


@pytest.fixture
def any_indexer(any_country):
    indexer_user = User.objects.create_user('indexer',
                                            first_name='Dexter',
                                            last_name='Indexer',
                                            email='noreply@comics.org',
                                            password='indexer')
    indexer = Indexer(user=indexer_user,
                      country=any_country)
    indexer.save()

    # We actually want the User object here, but it should have an Indexer
    # attached to act like a normal GCD user.  These tables get collapsed
    # in later versions of Django anyway (no more separate Profile).
    return indexer_user


@pytest.fixture
def any_changeset(any_indexer):
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['publisher'])
    c.save()
    return c


@pytest.mark.django_db
def test_create_add_revision(any_country, any_changeset):
    assert any_changeset.id > 0
    pr = PublisherRevision(changeset=any_changeset,
                           country=any_country,
                           keywords=KEYWORD_STRING,
                           **PUBLISHER_ADD_VALUES)
    pr.save()

    for k, v in PUBLISHER_ADD_VALUES.iteritems():
        assert getattr(pr, k) == v
    assert pr.keywords == KEYWORD_STRING
    assert pr.country == any_country
    assert pr.publisher is None

    assert pr.changeset == any_changeset
    assert pr.date_inferred is False

    assert pr.source is None
    assert pr.source_name == 'publisher'

    with mock.patch('apps.oi.models.update_count') as updater:
        pr.commit_to_display()
    assert updater.called_once_with('publishers', 1, pr.country)

    assert pr.publisher is not None
    assert pr.source is pr.publisher

    for k, v in PUBLISHER_ADD_VALUES.iteritems():
        assert getattr(pr.publisher, k) == v
    assert pr.publisher.brand_count == 0
    assert pr.publisher.series_count == 0
    assert pr.publisher.issue_count == 0

    keywords = [k for k in pr.publisher.keywords.names()]
    keywords.sort()
    assert keywords == KEYWORDS
    assert pr.publisher.country == any_country
