import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import IndiciaPublisher, Publisher
from apps.oi import states
from apps.oi.models import (
    BrandGroupRevision, Changeset, CTYPES, IndiciaPublisherRevision,
    IssueRevision, SeriesRevision, StoryRevision)
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
    revision = revision_class(parent=publisher, **years)
    return field_value(revision, field)


@pytest.mark.parametrize('revision_class',
                         [IndiciaPublisherRevision, BrandGroupRevision])
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


@pytest.mark.parametrize('revision_class',
                         [IndiciaPublisherRevision, BrandGroupRevision])
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


def test_no_note_without_publisher():
    revision = IndiciaPublisherRevision(year_began=1965)
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


EMPTY = '(note: empty)'


@pytest.mark.parametrize('field, value, expected', [
    ('price', '', EMPTY), ('price', '0.10 USD', '0.10 USD'),
    ('publication_date', '', EMPTY),
    ('publication_date', 'May 1947', 'May 1947')])
def test_note_on_empty_issue_field(field, value, expected):
    """An empty price or publication date of an issue gets a note."""
    revision = IssueRevision(**{field: value})
    revision.changed = {}
    assert field_value(revision, field) == expected


@pytest.mark.parametrize('field', ['price', 'publication_date'])
def test_no_note_on_previous_revision(field):
    """
    The previous revision, without the changed fields of a compared one,
    shows the state before the change without a note.
    """
    assert field_value(IssueRevision(), field) == ''


@pytest.mark.django_db
@pytest.mark.parametrize('page_count, uncertain, expected', [
    (None, False, EMPTY), (None, True, ''), (64, False, '64')])
def test_note_on_empty_page_count(any_indexer, page_count, uncertain,
                                  expected):
    """An empty page count gets a note unless it is uncertain."""
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    revision = IssueRevision(changeset=changeset, page_count=page_count,
                             page_count_uncertain=uncertain)
    revision.changed = {}
    assert field_value(revision, 'page_count') == expected


def test_no_note_on_empty_page_count_of_sequence():
    """The note is for issues, not for their sequences."""
    revision = StoryRevision(page_count=None)
    revision.changed = {}
    assert field_value(revision, 'page_count') == ''


def _compare_page(client, indexer, change_type, issues, **values):
    """
    The compare page of an open change of these issues with these values.
    """
    changeset = Changeset.objects.create(
      indexer=indexer, state=states.OPEN, change_type=change_type)
    for issue in issues:
        revision = IssueRevision.clone(data_object=issue, changeset=changeset)
        for field, value in values.items():
            setattr(revision, field, value)
        revision.save()
    client.force_login(indexer)
    response = client.get(reverse('compare', kwargs={'id': changeset.id}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_compare_page_notes_fields_the_change_empties(
        client, any_indexer, any_added_issue):
    """A field emptied by the change gets the note, the price too."""
    content = _compare_page(client, any_indexer, CTYPES['issue'],
                            [any_added_issue], price='', page_count=None,
                            publication_date='')

    # the changed price is shown as a diff, the note as added text
    assert "<span class='added'>%s</span>" % EMPTY in content
    assert content.count(EMPTY) == 3


@pytest.mark.django_db
def test_compare_page_notes_empty_fields_the_change_keeps(
        client, any_indexer, any_added_variant):
    """
    A field the change leaves empty gets the note in the column of the
    change only. The variant has no price, page count and publication date.
    """
    content = _compare_page(client, any_indexer, CTYPES['issue'],
                            [any_added_variant], notes='New notes')

    assert content.count(EMPTY) == 3


@pytest.mark.django_db
def test_bulk_change_notes_empty_price_once(
        client, any_indexer, any_added_issue, any_added_variant):
    """
    A bulk change shows the fields of one of its issues, so a price it
    empties gets one note, not one per issue.
    """
    content = _compare_page(client, any_indexer, CTYPES['issue_bulk'],
                            [any_added_issue, any_added_variant], price='',
                            page_count=64, publication_date='January 1947')

    assert content.count(EMPTY) == 1


@pytest.mark.django_db
def test_copy_page_notes_empty_fields_of_edited_issue(
        client, any_indexer, any_added_issue, any_added_variant):
    """
    The page that copies values from another issue notes the empty fields
    of the issue being edited, not of the issue the values come from.
    """
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    revision = IssueRevision.clone(data_object=any_added_variant,
                                   changeset=changeset)
    client.force_login(any_indexer)

    response = client.get(reverse('compare_issues_copy', kwargs={
      'issue_revision_id': revision.id, 'issue_id': any_added_issue.id}))

    assert response.status_code == 200
    assert response.content.decode().count(EMPTY) == 3
