# -*- coding: utf-8 -*-

import pytest

from django.contrib.auth.models import User

from apps.gcd.models import (
    Country, Language, Indexer, SeriesPublicationType, SeriesBondType)
from apps.oi import states
from apps.oi.models import (
    PublisherRevision, IndiciaPublisherRevision,
    BrandGroupRevision, BrandRevision, BrandUseRevision,
    SeriesRevision, SeriesBondRevision, Changeset, CTYPES)


@pytest.fixture
def keywords():
    kw = ['bar', 'foo']
    return {
        'list': kw,
        'string': '; '.join(kw),
    }


@pytest.fixture
def any_changeset(any_indexer):
    """
    Use this when the state of the changeset is irrelevant.
    """
    # TODO: A better strategy for dealing with changesets in fixtures.
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['publisher'])
    c.save()
    return c


@pytest.fixture
def any_adding_changeset(any_indexer):
    """
    Use this when adding new objects, and close when they are added.

    Can be used for multiple object adds as long as by the time the
    test cares about the state, all adds have been committed.  This
    is because each bit of code adding objects should assume that it
    can close the changeset once those objects are added, which means
    that there will be a period where the changeset is closed but
    additional objects still need to be committed.
    """
    # TODO: A better strategy for dealing with changesets in fixtures.
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['publisher'])  # CTYPE is arbitrary
    c.save()
    return c


@pytest.fixture
def any_editing_changeset(any_indexer):
    """
    Use this when editing an already-added object.
    """
    # TODO: A better strategy for dealing with changesets in fixtures.
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['publisher'])  # CTYPE is arbitrary
    c.save()
    return c


@pytest.fixture
def any_deleting_changeset(any_indexer):
    """
    Use this when deleting an already-added object.
    """
    # TODO: A better strategy for dealing with changesets in fixtures.
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['publisher'])  # CTYPE is arbitrary
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
def any_added_publisher_rev(any_country, any_adding_changeset,
                            publisher_add_values):
    """
    Returns a newly added publisher using values from any_publisher_add_values.
    """
    pr = PublisherRevision(changeset=any_adding_changeset,
                           **publisher_add_values)
    pr.save()
    return pr


@pytest.fixture
def any_added_publisher(any_added_publisher_rev):
    any_added_publisher_rev.commit_to_display()
    any_added_publisher_rev.changeset.state = states.APPROVED
    any_added_publisher_rev.changeset.save()
    return any_added_publisher_rev.publisher


@pytest.fixture
def indicia_publisher_add_values(any_country, any_added_publisher, keywords):
    return {
        'name': 'Test Indicia Publisher',
        'year_began': 1970,
        'year_ended': 2000,
        'year_began_uncertain': True,
        'year_ended_uncertain': False,
        'notes': 'indicia publisher add notes',
        'url': 'http://indicia.whatever.com',
        'keywords': keywords['string'],
        'country': any_country,
        'is_surrogate': True,
        'parent': any_added_publisher,
    }


@pytest.fixture
def any_added_indicia_publisher_rev(indicia_publisher_add_values,
                                    any_adding_changeset):
    ipr = IndiciaPublisherRevision(changeset=any_adding_changeset,
                                   **indicia_publisher_add_values)
    ipr.save()
    return ipr


@pytest.fixture
def any_added_indicia_publisher(any_added_indicia_publisher_rev):
    any_added_indicia_publisher_rev.commit_to_display()
    any_added_indicia_publisher_rev.changeset.state = states.APPROVED
    any_added_indicia_publisher_rev.changeset.save()
    return any_added_indicia_publisher_rev.indicia_publisher


@pytest.fixture
def brand_group_add_values(any_added_publisher, keywords):
    return {
        'name': 'Test Brand Group',
        'year_began': 1984,
        'year_ended': 1999,
        'year_began_uncertain': False,
        'year_ended_uncertain': True,
        'notes': 'brand group add notes',
        'url': 'http://group.whatever.com',
        'keywords': keywords['string'],
        'parent': any_added_publisher,
    }


@pytest.fixture
def any_added_brand_group_rev1(brand_group_add_values, any_adding_changeset):
    bgr = BrandGroupRevision(changeset=any_adding_changeset,
                             **brand_group_add_values)
    bgr.save()
    return bgr


@pytest.fixture
def any_added_brand_group_rev2(brand_group_add_values, any_adding_changeset):
    # Change a few.  No need to hold on to these as
    # anything that needs to test that something has the
    # right values for a brand group shoudl use rev1
    brand_group_add_values['name'] = ['Other Brand Group']
    brand_group_add_values['year_began'] = 1940
    brand_group_add_values['year_ended_uncertain'] = False
    bgr = BrandGroupRevision(changeset=any_adding_changeset,
                             **brand_group_add_values)
    bgr.save()
    return bgr


@pytest.fixture
def any_added_brand_group1(any_added_brand_group_rev1):
    any_added_brand_group_rev1.commit_to_display()
    any_added_brand_group_rev1.changeset.state = states.APPROVED
    any_added_brand_group_rev1.changeset.save()
    return any_added_brand_group_rev1.brand_group


@pytest.fixture
def any_added_brand_group2(any_added_brand_group_rev2):
    any_added_brand_group_rev2.commit_to_display()
    any_added_brand_group_rev2.changeset.state = states.APPROVED
    any_added_brand_group_rev2.changeset.save()
    return any_added_brand_group_rev2.brand_group


@pytest.fixture
def brand_add_values(keywords):
    return {
        'name': 'Test Brand ',
        'year_began': 1988,
        'year_ended': 1990,
        'year_began_uncertain': False,
        'year_ended_uncertain': False,
        'notes': 'brand add notes',
        'url': 'http://brand.whatever.com',
        'keywords': keywords['string'],
    }


@pytest.fixture
def any_added_brand_rev(brand_add_values, any_adding_changeset,
                        any_added_brand_group1):
    br = BrandRevision(changeset=any_adding_changeset,
                       **brand_add_values)
    br.save()
    br.group.add(*(any_added_brand_group1,))
    return br


@pytest.fixture
def any_added_brand(any_added_brand_rev):
    any_added_brand_rev.commit_to_display()
    any_added_brand_rev.changeset.state = states.APPROVED
    any_added_brand_rev.changeset.save()
    return any_added_brand_rev.brand


@pytest.fixture
def brand_use_add_values(any_added_publisher, any_added_brand):
    return {
        'publisher': any_added_publisher,
        'emblem': any_added_brand,
        'year_began': 1970,
        'year_ended': 1975,
        'year_began_uncertain': True,
        'year_ended_uncertain': True,
        'notes': 'The contents of these notes are unimportant',
    }


@pytest.fixture
def any_added_brand_use_rev(brand_use_add_values, any_adding_changeset):
    bur = BrandUseRevision(changeset=any_adding_changeset,
                           **brand_use_add_values)
    bur.save()
    return bur


@pytest.fixture
def any_added_brand_use(any_added_brand_use_rev):
    any_added_brand_use_rev.commit_to_display()
    any_added_brand_use_rev.changeset.state = states.APPROVED
    any_added_brand_use_rev.changeset.save()
    return any_added_brand_use_rev.brand_use


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
def any_added_series_rev(any_adding_changeset, series_add_values):
    sr = SeriesRevision(changeset=any_adding_changeset, leading_article=True,
                        **series_add_values)
    sr.save()
    return sr


@pytest.fixture
def any_added_series(any_added_series_rev):
    any_added_series_rev.commit_to_display()
    any_added_series_rev.changeset.state = states.APPROVED
    any_added_series_rev.changeset.save()
    return any_added_series_rev.series


@pytest.fixture
def series_bond_add_values(series_add_values, any_adding_changeset):
    # This does series-only bonds, issue-level bonds to be added later.
    origin_series_values = series_add_values.copy()
    origin_series_values['name'] = 'Origin Series'
    origin_rev = SeriesRevision.objects.create(changeset=any_adding_changeset,
                                               **origin_series_values)
    origin_rev.commit_to_display()

    target_series_values = series_add_values.copy()
    target_series_values['name'] = 'Target Series'
    target_rev = SeriesRevision.objects.create(changeset=any_adding_changeset,
                                               **target_series_values)
    target_rev.commit_to_display()

    any_bond_type = SeriesBondType.objects.get_or_create(name='any type')[0]
    return {
        'origin': origin_rev.source,
        'target': target_rev.source,
        'bond_type': any_bond_type,
        'notes': 'blah blah wahtever',
    }


@pytest.fixture
def any_added_series_bond_rev(series_bond_add_values, any_adding_changeset):
    sbr = SeriesBondRevision(changeset=any_adding_changeset,
                             **series_bond_add_values)
    sbr.save()
    return sbr


@pytest.fixture
def any_added_series_bond(any_added_series_bond_rev):
    any_added_series_bond_rev.commit_to_display()
    any_added_series_bond_rev.changeset.state = states.APPROVED
    any_added_series_bond_rev.changeset.save()
    return any_added_series_bond_rev.series_bond
