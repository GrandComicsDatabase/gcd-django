import pytest

from django.urls import reverse

from apps.gcd.models import IndiciaPublisher
from apps.oi import states
from apps.oi.models import (
    Changeset, CTYPES, IndiciaPublisherRevision, IssueRevision,
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
