# -*- coding: utf-8 -*-

import pytest

from django.contrib.auth.models import User

from apps.gcd.models import Country, Language, Indexer, SeriesPublicationType
from apps.oi import states
from apps.oi.models import PublisherRevision, SeriesRevision, Changeset, CTYPES


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


@pytest.fixture
def any_added_publisher(any_added_publisher_rev):
    # TODO: This leaves the changeset open, in part because changeset
    #       state transitions have not yet been implemented.  Will have
    #       to figure out how to manage that as tests get more complex.
    #       Right now nothing cares about changeset state.
    any_added_publisher_rev.commit_to_display()
    return any_added_publisher_rev.publisher


@pytest.fixture
def series_add_values(any_country, any_language,
                      any_added_publisher, keywords):
    series_pub_type = SeriesPublicationType.objects \
                                           .get_or_create(name='magazine')[0]

    return {
        'name': 'The Test Series',
        'color': 'full color',
        'dimensions': '7" x 11"',
        'paper_stock': 'newsprint',
        'binding': 'saddle stitched',
        'publishing_format': 'limited series',
        'publication_type': series_pub_type,
        'is_singleton': False,
        'notes': 'blah blah whatever',
        'year_began': 1990,
        'year_ended': None,
        'year_began_uncertain': False,
        'year_ended_uncertain': False,
        'is_current': True,
        'publication_notes': 'more stuff goes here',
        'has_barcode': True,
        'has_indicia_frequency': True,
        'has_isbn': True,
        'has_volume': True,
        'has_issue_title': True,
        'has_rating': True,
        'is_comics_publication': True,
        'country': any_country,
        'language': any_language,
        'publisher': any_added_publisher,
        'keywords': keywords['string'],
    }


@pytest.fixture
def series_form_fields():
    return [
        'name',
        'leading_article',
        'imprint',
        'format',
        'color',
        'dimensions',
        'paper_stock',
        'binding',
        'publishing_format',
        'publication_type',
        'is_singleton',
        'year_began',
        'year_began_uncertain',
        'year_ended',
        'year_ended_uncertain',
        'is_current',
        'country',
        'language',
        'has_barcode',
        'has_indicia_frequency',
        'has_isbn',
        'has_issue_title',
        'has_volume',
        'has_rating',
        'is_comics_publication',
        'tracking_notes',
        'notes',
        'keywords',
        'publication_notes',
    ]


@pytest.fixture
def any_added_series_rev(any_changeset, series_add_values):
    sr = SeriesRevision(changeset=any_changeset, leading_article=True,
                        **series_add_values)
    sr.save()
    return sr


@pytest.fixture
def any_added_series(any_added_series_rev):
    # TODO: This leaves the changeset open, see any_added_series()
    any_added_series_rev.commit_to_display()
    return any_added_series_rev.series
