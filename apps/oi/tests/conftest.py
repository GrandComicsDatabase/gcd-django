# -*- coding: utf-8 -*-

import pytest

from django.contrib.auth.models import User

from apps.gcd.models import Country, Language, Indexer
from apps.oi import states
from apps.oi.models import PublisherRevision, Changeset, CTYPES


@pytest.fixture
def keywords():
    kw = ['bar', 'foo']
    return {
        'list': kw,
        'string': '; '.join(kw),
    }


@pytest.fixture
def any_changeset(any_indexer):
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['publisher'])
    c.save()
    return c


@pytest.fixture
def any_country():
    c = Country.objects.get_or_create(code='XZZ', name='Test Country')
    return c[0]


@pytest.fixture
def any_language():
    l = Language.objects.get_or_create(code='XZZ', name='Test Language')
    return l[0]


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
def publisher_add_values(any_country, keywords):
    return {
        'name': 'Test Publisher',
        'year_began': 1960,
        'year_ended': None,
        'year_began_uncertain': True,
        'year_ended_uncertain': False,
        'notes': 'publisher add notes',
        'url': 'http://whatever.com',
        'keywords': keywords['string'],
        'country': any_country,
    }


@pytest.fixture
def publisher_form_fields():
    return [
        'name',
        'year_began',
        'year_began_uncertain',
        'year_ended',
        'year_ended_uncertain',
        'country',
        'url',
        'notes',
        'keywords',
        'is_master',
        'parent',
    ]


@pytest.fixture
def any_added_publisher_rev(any_country, any_changeset, publisher_add_values):
    """
    Returns a newly added publisher using values from any_publisher_add_values.
    """
    pr = PublisherRevision(changeset=any_changeset, **publisher_add_values)
    pr.save()
    return pr
