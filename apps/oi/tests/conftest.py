# -*- coding: utf-8 -*-


import pytest

from django.db import models, connections
from django.contrib.auth.models import User
from taggit.managers import TaggableManager
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from apps.gcd.models import (
    SeriesPublicationType, SeriesBondType, Issue, StoryType)
from apps.stddata.models import Country, Language
from apps.stats.models import CountStats
from apps.indexer.models import Indexer
from apps.gcd.models.gcddata import GcdData
from apps.oi import states
from apps.oi.models import (
    Revision, PublisherRevision, IndiciaPublisherRevision,
    BrandGroupRevision, BrandRevision, BrandUseRevision,
    SeriesRevision, SeriesBondRevision, IssueRevision, StoryRevision,
    Changeset, CTYPES)


@pytest.fixture
def keywords():
    kw = ['bar', 'foo']
    return {
        'list': kw,
        'string': '; '.join(kw),
    }


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        CountStats.objects.init_stats()
        CountStats.objects.init_stats(country=any_country())

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
def any_variant_adding_changeset(any_indexer):
    """
    Use this when adding a varaint.
    """
    # TODO: A better strategy for dealing with changesets in fixtures.
    c = Changeset(state=states.OPEN,
                  indexer=any_indexer,
                  change_type=CTYPES['variant_add'])
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


@pytest.fixture
def issue_add_values(any_adding_changeset, any_country, any_language,
                     any_added_publisher, any_added_indicia_publisher,
                     any_added_brand, keywords):
    """
    Add values for a pretty basic issue.  All conditional fields are turned
    on because turning them off produces some strange behavior.
    See https://github.com/GrandComicsDatabase/gcd-django/issues/116
    """
    series_pub_type = SeriesPublicationType.objects \
                                           .get_or_create(name='magazine')[0]
    series_rev = SeriesRevision.objects.create(
        changeset=any_adding_changeset,
        name='Series for Issues',
        year_began=1939,
        publication_type=series_pub_type,
        is_comics_publication=True,
        country=any_country,
        language=any_language,
        publisher=any_added_publisher,
        has_volume=True,
        has_issue_title=True,
        has_indicia_frequency=True,
        has_barcode=True,
        has_isbn=True,
        has_rating=True,
    )
    series_rev.commit_to_display()

    return {
        'number': '42',
        'no_title': True,
        'no_volume': True,
        'series': series_rev.series,
        'indicia_publisher': any_added_indicia_publisher,
        'brand': any_added_brand,
        'publication_date': 'January 1947',
        'key_date': '1947-01-00',
        'year_on_sale': 1946,
        'month_on_sale': 11,
        'day_on_sale': 23,
        'on_sale_date_uncertain': True,
        'no_isbn': True,
        'no_barcode': True,
        'no_rating': True,
        'indicia_frequency': 'monthly',
        'price': '0.10 USD',
        'page_count': 64,
        'editing': 'Some One',
        'notes': 'These notes are fascinating',
        'keywords': keywords['string'],
    }


@pytest.fixture
def any_added_issue_rev(any_adding_changeset, issue_add_values):
    rev = IssueRevision(changeset=any_adding_changeset, **issue_add_values)
    rev.save()
    return rev


@pytest.fixture
def any_added_issue(any_added_issue_rev):
    any_added_issue_rev.commit_to_display()
    any_added_issue_rev.changeset.state = states.APPROVED
    any_added_issue_rev.changeset.save()
    return any_added_issue_rev.issue


@pytest.fixture
def variant_add_values(any_added_issue):
    return {
        'variant_of': any_added_issue,
        'variant_name': 'varied variant',
        'series': any_added_issue.series,
        'indicia_publisher': any_added_issue.indicia_publisher,
        'brand': any_added_issue.brand,
    }


@pytest.fixture
def any_added_variant_rev(any_variant_adding_changeset, variant_add_values):
    rev = IssueRevision(changeset=any_variant_adding_changeset,
                        **variant_add_values)
    rev.save()
    return IssueRevision.objects.get(pk=rev.pk)


@pytest.fixture
def any_added_variant(any_added_variant_rev):
    any_added_variant_rev.commit_to_display()
    any_added_variant_rev.changeset.state = states.APPROVED
    any_added_variant_rev.changeset.save()
    return Issue.objects.get(pk=any_added_variant_rev.issue.pk)


@pytest.fixture
def story_add_values(any_added_issue, keywords):
    story_type = StoryType.objects.get(name='comic story')

    return {
        'title': 'Test Story Title',
        'title_inferred': True,
        'issue': any_added_issue,
        'feature': 'Test Feature',
        'type': story_type,
        'sequence_number': 1,
        'page_count': 8,
        'page_count_uncertain': True,
        'script': 'Test Person One',
        'pencils': 'Test Person Two',
        'inks': 'Test Person Three',
        'colors': '',
        'no_colors': True,
        'letters': 'Test Person Four',
        'editing': '',
        'no_editing': True,
        'job_number': '1234',
        'genre': 'something contentious',
        'characters': 'Blah Blah [Whatever]',
        'synopsis': 'Stuff happened.',
        'reprint_notes': 'Not bothering to format this properly.',
        'notes': 'Random extra info',
        'keywords': keywords['string'],
    }


@pytest.fixture
def any_added_story_rev(any_adding_changeset, story_add_values):
    rev = StoryRevision(changeset=any_adding_changeset, **story_add_values)
    rev.save()
    return rev


@pytest.fixture
def any_added_story(any_added_story_rev):
    any_added_story_rev.commit_to_display()
    any_added_story_rev.changeset.state = states.APPROVED
    any_added_story_rev.changeset.save()
    return any_added_story_rev.story


@pytest.fixture
def any_edit_story_rev(any_added_story, any_editing_changeset):
    rev = StoryRevision.clone(data_object=any_added_story,
                              changeset=any_editing_changeset)
    return rev
