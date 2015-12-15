# -*- coding: utf-8 -*-

import pytest

from django.contrib.auth.models import User

from apps.gcd.models import Country, Language, Indexer, SeriesPublicationType
from apps.oi import states
from apps.oi.models import (
    Revision, PublisherRevision, IndiciaPublisherRevision,
    BrandGroupRevision, BrandRevision, BrandUseRevision,
    SeriesRevision, Changeset, CTYPES)


# Make a non-abstract class that acts like a Revision, but con be
# instantiated (otherwise the OneToOneField has problems) and can
# have a manager, i.e. DummyRevision.objects.
#
# This needs to be in conftests.py even though it's trivial because
# if it is repeated in different test files, Django thinks there
# are duplicate models being declared.
class DummyRevision(Revision):
    pass


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
                                    any_changeset):
    ipr = IndiciaPublisherRevision(changeset=any_changeset,
                                   **indicia_publisher_add_values)
    ipr.save()
    return ipr


@pytest.fixture
def any_added_indicia_publisher(any_added_indicia_publisher_rev):
    any_added_indicia_publisher_rev.commit_to_display()
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
def any_added_brand_group_rev1(brand_group_add_values, any_changeset):
    bgr = BrandGroupRevision(changeset=any_changeset,
                             **brand_group_add_values)
    bgr.save()
    return bgr


@pytest.fixture
def any_added_brand_group_rev2(brand_group_add_values, any_changeset):
    # Change a few.  No need to hold on to these as
    # anything that needs to test that something has the
    # right values for a brand group shoudl use rev1
    brand_group_add_values['name'] = ['Other Brand Group']
    brand_group_add_values['year_began'] = 1940
    brand_group_add_values['year_ended_uncertain'] = False
    bgr = BrandGroupRevision(changeset=any_changeset,
                             **brand_group_add_values)
    bgr.save()
    return bgr


@pytest.fixture
def any_added_brand_group1(any_added_brand_group_rev1):
    any_added_brand_group_rev1.commit_to_display()
    return any_added_brand_group_rev1.brand_group


@pytest.fixture
def any_added_brand_group2(any_added_brand_group_rev2):
    any_added_brand_group_rev2.commit_to_display()
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
def any_added_brand_rev(brand_add_values, any_changeset,
                        any_added_brand_group1):
    br = BrandRevision(changeset=any_changeset,
                       **brand_add_values)
    br.save()
    br.group.add(*(any_added_brand_group1,))
    return br


@pytest.fixture
def any_added_brand(any_added_brand_rev):
    any_added_brand_rev.commit_to_display()
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
def any_added_brand_use_rev(brand_use_add_values, any_changeset):
    bur = BrandUseRevision(changeset=any_changeset,
                           **brand_use_add_values)
    bur.save()
    return bur


@pytest.fixture
def any_added_brand_use(any_added_brand_use_rev):
    any_added_brand_use_rev.commit_to_display()
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
