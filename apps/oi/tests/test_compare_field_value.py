import pytest

from django.urls import reverse

from apps.gcd.models import BrandGroup, BrandUse, IndiciaPublisher, Publisher
from apps.oi import states
from apps.oi.models import (
    BrandGroupRevision, BrandUseRevision, Changeset, CTYPES,
    IndiciaPublisherRevision, IssueRevision, PublisherRevision,
    SeriesRevision)
from apps.oi.templatetags.compare import field_value


@pytest.mark.parametrize('field', ['has_about_comics',
                                   'has_publisher_code_number'])
@pytest.mark.parametrize('value, expected', [(True, 'Yes'), (False, 'No')])
def test_series_flags_show_yes_no(field, value, expected):
    revision = SeriesRevision(**{field: value})
    assert field_value(revision, field) == expected


def _indicia_publisher_value(key_date, **years):
    publisher = IndiciaPublisher(id=1, name='Ink & Co', **years)
    revision = IssueRevision(key_date=key_date, indicia_publisher=publisher)
    return field_value(revision, 'indicia_publisher')


@pytest.mark.parametrize('key_date, years, expected', [
    ('1965-01-00', {'year_began': 1970, 'year_ended': 2000},
     'used in 1965, before its first year 1970'),
    ('2001-01-00', {'year_began': 1970, 'year_ended': 2000},
     'used in 2001, after its last year 2000'),
    ('2001.01.00', {'year_ended': 2000},
     'used in 2001, after its last year 2000'),
    # the side with a certain year is still compared
    ('2001-01-00', {'year_began': 1970, 'year_began_uncertain': True,
                    'year_ended': 2000},
     'used in 2001, after its last year 2000'),
    ('1965-01-00', {'year_began': 1970, 'year_ended': 2000,
                    'year_ended_uncertain': True},
     'used in 1965, before its first year 1970'),
])
def test_note_when_key_date_outside_indicia_publisher_years(
        key_date, years, expected):
    assert ('<br><br>Note: Indicia publisher "Ink &amp; Co" %s.' % expected
            in _indicia_publisher_value(key_date, **years))


@pytest.mark.parametrize('key_date, years', [
    # inside the years, first and last year included
    ('1970-01-00', {'year_began': 1970, 'year_ended': 2000}),
    ('2000-12-00', {'year_began': 1970, 'year_ended': 2000}),
    # no end year: still active
    ('2030-01-00', {'year_began': 1970, 'year_ended': None}),
    # no start year, or no years at all
    ('1950-01-00', {'year_began': None, 'year_ended': 2000}),
    ('1950-01-00', {'year_began': None, 'year_ended': None}),
    # uncertain years
    ('1965-01-00', {'year_began': 1970, 'year_began_uncertain': True}),
    ('2001-01-00', {'year_ended': 2000, 'year_ended_uncertain': True}),
    # no usable year in the key date
    ('', {'year_began': 1970, 'year_ended': 2000}),
    ('19??-01-00', {'year_began': 1970, 'year_ended': 2000}),
    ('199', {'year_began': 1970, 'year_ended': 2000}),
    ('0000-00-00', {'year_began': 1970, 'year_ended': 2000}),
])
def test_no_note_when_data_shows_no_problem(key_date, years):
    value = _indicia_publisher_value(key_date, **years)
    assert 'Ink &amp; Co</a>' in value
    assert 'Note' not in value


def test_no_note_without_indicia_publisher():
    revision = IssueRevision(key_date='1965-01-00')
    assert field_value(revision, 'indicia_publisher') == ''


def test_no_note_on_a_revision_without_key_date():
    publisher = IndiciaPublisher(id=1, name='Ink', year_began=1970)
    revision = IndiciaPublisherRevision(indicia_publisher=publisher)
    assert 'Note' not in field_value(revision, 'indicia_publisher')


@pytest.mark.django_db
def test_compare_page_notes_key_date_outside_years(
        client, any_indexer, any_added_issue, any_added_brand,
        second_brand_same_group):
    # the key date is 1947-01-00, any_added_brand is from 1988 to 1990
    publisher = any_added_issue.indicia_publisher
    publisher.year_began_uncertain = False
    publisher.save()
    second_brand_same_group.year_began = 1940
    second_brand_same_group.save()
    any_added_issue.brand_emblem.add(second_brand_same_group)
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    IssueRevision.clone(data_object=any_added_issue, changeset=changeset)
    client.force_login(any_indexer)

    response = client.get(reverse('compare', kwargs={'id': changeset.id}))

    assert response.status_code == 200
    content = response.content.decode()
    assert ('Note: Indicia publisher "%s" used in 1947, before its first '
            'year 1970.' % publisher.name) in content
    assert ('Note: Brand emblem "%s" used in 1947, before its first '
            'year 1988.' % any_added_brand.name) in content
    assert 'Note: Brand emblem "%s"' % second_brand_same_group.name \
        not in content


def _year_value(revision_class, field, years, publisher_years):
    publisher = Publisher(id=1, name='Sample Publisher', **publisher_years)
    link = 'publisher' if revision_class is BrandUseRevision else 'parent'
    revision = revision_class(**{link: publisher}, **years)
    return field_value(revision, field)


CHILD_REVISIONS = [IndiciaPublisherRevision, BrandGroupRevision,
                   BrandUseRevision]


@pytest.mark.parametrize('revision_class', CHILD_REVISIONS)
@pytest.mark.parametrize('field, years, expected', [
    ('year_began', {'year_began': 1965},
     '1965 (note: before the first year 1970 of the publisher)'),
    ('year_ended', {'year_ended': 2005},
     '2005 (note: after the last year 2000 of the publisher)'),
    # each year is compared with both years of the publisher
    ('year_began', {'year_began': 2005},
     '2005 (note: after the last year 2000 of the publisher)'),
    ('year_ended', {'year_ended': 1965},
     '1965 (note: before the first year 1970 of the publisher)'),
])
def test_note_when_year_outside_publisher_years(revision_class, field, years,
                                                expected):
    publisher_years = {'year_began': 1970, 'year_ended': 2000}
    assert _year_value(revision_class, field, years,
                       publisher_years) == expected


@pytest.mark.parametrize('revision_class', CHILD_REVISIONS)
@pytest.mark.parametrize('field, years, publisher_years', [
    # inside the years, first and last year included
    ('year_began', {'year_began': 1970}, {'year_began': 1970}),
    ('year_ended', {'year_ended': 2000}, {'year_ended': 2000}),
    # a blank year on either side
    ('year_began', {'year_began': None}, {'year_began': 1970}),
    ('year_ended', {'year_ended': 2005}, {'year_ended': None}),
    # an uncertain year on either side
    ('year_began', {'year_began': 1965, 'year_began_uncertain': True},
     {'year_began': 1970}),
    ('year_ended', {'year_ended': 2005},
     {'year_ended': 2000, 'year_ended_uncertain': True}),
    # the other year of the publisher: equal, or uncertain
    ('year_began', {'year_began': 2000}, {'year_ended': 2000}),
    ('year_ended', {'year_ended': 1970}, {'year_began': 1970}),
    ('year_began', {'year_began': 2005},
     {'year_ended': 2000, 'year_ended_uncertain': True}),
    ('year_ended', {'year_ended': 1965},
     {'year_began': 1970, 'year_began_uncertain': True}),
])
def test_no_note_when_years_show_no_problem(revision_class, field, years,
                                            publisher_years):
    assert _year_value(revision_class, field, years,
                       publisher_years) == years[field]


@pytest.mark.parametrize('revision_class',
                         CHILD_REVISIONS + [PublisherRevision])
def test_no_note_without_publisher(revision_class):
    revision = revision_class(year_began=1965)
    assert field_value(revision, 'year_began') == 1965


@pytest.mark.django_db
def test_compare_page_notes_years_outside_publisher_years(
        client, any_indexer, any_added_indicia_publisher):
    # the indicia publisher runs from 1970 (uncertain) to 2000
    publisher = any_added_indicia_publisher.parent
    publisher.year_began = 1975
    publisher.year_began_uncertain = False
    publisher.year_ended = 1995
    publisher.save()
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN,
      change_type=CTYPES['indicia_publisher'])
    revision = IndiciaPublisherRevision.clone(
      data_object=any_added_indicia_publisher, changeset=changeset)
    revision.year_began_uncertain = False
    revision.save()
    client.force_login(any_indexer)

    response = client.get(reverse('compare', kwargs={'id': changeset.id}))

    assert response.status_code == 200
    content = response.content.decode()
    # each column uses the years of its own revision
    assert content.count(
      '2000 (note: after the last year 1995 of the publisher)') == 2
    assert content.count(
      '1970 (note: before the first year 1975 of the publisher)') == 1


@pytest.mark.django_db
def test_compare_page_notes_brand_use_years_outside_publisher_years(
        client, any_indexer, any_added_brand_use):
    '''The compare page of a brand use change shows the note.'''
    # the brand use runs from 1970 to 1975, both uncertain
    publisher = any_added_brand_use.publisher
    publisher.year_began = 1972
    publisher.year_began_uncertain = False
    publisher.save()
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['brand_use'])
    revision = BrandUseRevision.clone(data_object=any_added_brand_use,
                                      changeset=changeset)
    revision.year_began_uncertain = False
    revision.save()
    client.force_login(any_indexer)

    response = client.get(reverse('compare', kwargs={'id': changeset.id}))

    assert response.status_code == 200
    assert response.content.decode().count(
      '1970 (note: before the first year 1972 of the publisher)') == 1


@pytest.fixture
def publisher_with_children(any_added_indicia_publisher,
                            any_added_brand_group1, any_added_brand_use,
                            second_brand_same_group):
    '''
    A publisher with an indicia publisher from 1975 to 2000, a brand group
    from 1984 to 1999 (uncertain), and brand uses from 1970 to 1975 and
    from 1978 to 1985.
    '''
    publisher = any_added_brand_use.publisher
    # adding a brand group, or a brand to a group, also adds a brand use
    # with its years: keep only the uses below
    BrandUse.objects.filter(publisher=publisher).exclude(
      id=any_added_brand_use.id).delete()
    IndiciaPublisher.objects.filter(parent=publisher).update(
      year_began=1975, year_began_uncertain=False)
    BrandUse.objects.filter(publisher=publisher).update(
      year_began_uncertain=False, year_ended_uncertain=False)
    BrandUse.objects.create(publisher=publisher,
                            emblem=second_brand_same_group,
                            year_began=1978, year_ended=1985)
    return publisher


def _publisher_value(publisher, field, **years):
    '''The compare value of a field of a publisher revision with years.'''
    revision = PublisherRevision(publisher=publisher, **years)
    return field_value(revision, field)


@pytest.mark.django_db
@pytest.mark.parametrize('field, years, expected', [
    ('year_began', {'year_began': 1980},
     '1980 (note: 1 indicia publisher and 2 brand uses have a year '
     'before it)'),
    # the last year 1999 of the brand group is uncertain
    ('year_ended', {'year_ended': 1990},
     '1990 (note: 1 indicia publisher has a year after it)'),
    ('year_began', {'year_began': 1990},
     '1990 (note: 1 indicia publisher, 1 brand group and 2 brand uses '
     'have a year before it)'),
    ('year_ended', {'year_ended': 1980},
     '1980 (note: 1 indicia publisher, 1 brand group and 1 brand use '
     'have a year after it)'),
])
def test_note_when_years_of_children_outside_publisher_years(
        publisher_with_children, field, years, expected):
    '''The note counts the records with a certain year outside.'''
    assert _publisher_value(publisher_with_children, field,
                            **years) == expected


@pytest.mark.django_db
@pytest.mark.parametrize('field, years', [
    # the first and the last year count as inside
    ('year_began', {'year_began': 1970}),
    ('year_ended', {'year_ended': 2000}),
    # a blank or uncertain year of the publisher
    ('year_began', {'year_began': None}),
    ('year_began', {'year_began': 1990, 'year_began_uncertain': True}),
    ('year_ended', {'year_ended': 1980, 'year_ended_uncertain': True}),
])
def test_no_note_when_years_of_children_show_no_problem(
        publisher_with_children, field, years):
    '''No note on a year at the edge, blank or uncertain.'''
    assert _publisher_value(publisher_with_children, field,
                            **years) == years[field]


@pytest.mark.django_db
def test_note_leaves_out_deleted_children(publisher_with_children):
    '''Deleted indicia publishers and brand groups are not counted.'''
    IndiciaPublisher.objects.filter(parent=publisher_with_children).update(
      deleted=True)
    BrandGroup.objects.filter(parent=publisher_with_children).update(
      deleted=True)
    assert _publisher_value(publisher_with_children, 'year_ended',
                            year_ended=1980) == \
        '1980 (note: 1 brand use has a year after it)'


@pytest.mark.django_db
def test_compare_page_notes_children_years_outside_publisher_years(
        client, any_indexer, publisher_with_children):
    '''The compare page of a publisher change shows the note.'''
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['publisher'])
    revision = PublisherRevision.clone(data_object=publisher_with_children,
                                       changeset=changeset)
    revision.year_began = 1980
    revision.year_began_uncertain = False
    revision.save()
    client.force_login(any_indexer)

    response = client.get(reverse('compare', kwargs={'id': changeset.id}))

    assert response.status_code == 200
    assert ('1980 (note: 1 indicia publisher and 2 brand uses have a year '
            'before it)') in response.content.decode()
