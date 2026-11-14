"""
The page of a bulk change: the notes of the compare page of one issue on
a key date outside the years of its indicia publisher or brand emblems.
"""
import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import strip_tags

from apps.oi.models import (
    BrandRevision, IndiciaPublisherRevision, IssueRevision)
from apps.oi.templatetags.compare import field_value


def note(label, name, used, words):
    """A note as the compare page of one issue writes it."""
    return '<br><br>Note: %s "%s" used in %d, %s.' % (label, name, used,
                                                      words)


def page(client, changeset):
    """The page of a change, seen by its indexer."""
    client.force_login(changeset.indexer)
    return client.get(reverse('compare', kwargs={'id': changeset.id}))


def cells(response, label):
    """The Old and New cells of the rows of one field, in page order."""
    return [(old, new) for revision, name, fields in response.context['rows']
            for field, old, new in fields if field == label]


@pytest.fixture
def add_indicia_publisher(indicia_publisher_add_values,
                          any_adding_changeset):
    """
    Return a function that adds an approved indicia publisher with the
    given name and years, certain unless told.
    """
    def add(name, began, ended, began_uncertain=False,
            ended_uncertain=False):
        """Add the indicia publisher and return it."""
        revision = IndiciaPublisherRevision(
          changeset=any_adding_changeset,
          **dict(indicia_publisher_add_values, name=name, year_began=began,
                 year_ended=ended, year_began_uncertain=began_uncertain,
                 year_ended_uncertain=ended_uncertain))
        revision.save()
        revision.commit_to_display()
        return revision.indicia_publisher
    return add


@pytest.fixture
def add_emblem(brand_add_values, any_adding_changeset,
               any_added_brand_group1):
    """
    Return a function that adds an approved brand emblem with the given
    name and certain years.
    """
    def add(name, began, ended):
        """Add the brand emblem and return it."""
        revision = BrandRevision(
          changeset=any_adding_changeset,
          **dict(brand_add_values, name=name, year_began=began,
                 year_ended=ended))
        revision.save()
        revision.group.add(any_added_brand_group1)
        revision.commit_to_display()
        return revision.brand
    return add


@pytest.fixture
def add_issues(any_added_issue, any_adding_changeset):
    """
    Return a function that adds approved issues to the series of
    any_added_issue, with the given key date, indicia publisher and
    brand emblems.
    """
    issues = [any_added_issue]

    def add(count, key_date, indicia_publisher, emblems=()):
        """Add count issues and return them."""
        for _ in range(count):
            revision = IssueRevision(
              changeset=any_adding_changeset, number=str(len(issues) + 42),
              after=issues[-1], series=any_added_issue.series,
              no_title=True, no_volume=True, key_date=key_date,
              indicia_publisher=indicia_publisher, price='0.10 USD',
              indicia_frequency='monthly')
            revision.save()
            revision.brand_emblem.set(emblems)
            revision.commit_to_display()
            issues.append(revision.issue)
        return issues[-count:]
    return add


@pytest.fixture
def years_publisher(add_indicia_publisher):
    """An indicia publisher used from 1980 to 1990."""
    return add_indicia_publisher('Years Publisher', 1980, 1990)


@pytest.mark.django_db
@pytest.mark.parametrize('key_date, words', [
  ('1995-01-00', 'after its last year 1990'),
  ('1975-01-00', 'before its first year 1980')])
def test_new_key_date_outside_the_years(client, bulk_change, add_issues,
                                        years_publisher, key_date, words):
    """
    A key date moved outside the years of the indicia publisher ends the
    New cell of the Key Date row with the note; the Old cell has none.
    """
    [issue] = add_issues(1, '1985-01-00', years_publisher)
    changeset = bulk_change([issue], IssueRevision, key_date=key_date)

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Key Date')
    expected = note('Indicia publisher', 'Years Publisher',
                    int(key_date[:4]), words)
    assert new.endswith(expected)
    assert strip_tags(new[:-len(expected)]) == key_date
    assert 'Note:' not in old


@pytest.mark.django_db
def test_note_as_on_the_page_of_one_issue(client, bulk_change, add_issues,
                                          years_publisher):
    """
    The note is, character by character, the one that the compare page
    of one issue shows for the indicia publisher of the same revision.
    """
    [issue] = add_issues(1, '1985-01-00', years_publisher)
    changeset = bulk_change([issue], IssueRevision, key_date='1995-01-00')

    response = page(client, changeset)

    [(revision, name, fields)] = response.context['rows']
    [(old, new)] = cells(response, 'Key Date')
    shown = field_value(revision, 'indicia_publisher')
    assert '<br><br>Note: ' in new
    assert new[new.index('<br><br>Note: '):] == \
        shown[shown.index('<br><br>Note: '):]


@pytest.mark.django_db
def test_note_in_the_row_of_the_indicia_publisher(client, bulk_change,
                                                  add_issues,
                                                  add_indicia_publisher,
                                                  years_publisher):
    """
    When the key date and the indicia publisher change, the note is in
    the Indicia Publisher row; the Key Date cells are the plain values.
    """
    other = add_indicia_publisher('Older Publisher', 1960, 1970)
    [issue] = add_issues(1, '1985-01-00', years_publisher)
    changeset = bulk_change([issue], IssueRevision, key_date='1995-01-00',
                            indicia_publisher=other)

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Indicia Publisher')
    assert new == "<span class='added'>Older Publisher</span>" + note(
      'Indicia publisher', 'Older Publisher', 1995, 'after its last year 1970')
    assert old == "<span class='deleted'>Years Publisher</span>"
    [(old, new)] = cells(response, 'Key Date')
    assert strip_tags(old) == '1985-01-00'
    assert strip_tags(new) == '1995-01-00'
    assert '<br>' not in old + new


@pytest.mark.django_db
@pytest.mark.parametrize('key_date, new_note', [
  ('1985-01-00', ''),
  ('1997-01-00', note('Indicia publisher', 'Years Publisher', 1997,
                      'after its last year 1990'))])
def test_old_key_date_outside_the_years(client, bulk_change, add_issues,
                                        years_publisher, key_date,
                                        new_note):
    """
    An issue stored outside the years has the note in the Old cell, by
    its old key date; a new key date inside the years has none, one
    outside has its own.
    """
    [issue] = add_issues(1, '1995-01-00', years_publisher)
    changeset = bulk_change([issue], IssueRevision, key_date=key_date)

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Key Date')
    old_note = note('Indicia publisher', 'Years Publisher', 1995,
                    'after its last year 1990')
    assert old.endswith(old_note)
    assert strip_tags(old[:-len(old_note)]) == '1995-01-00'
    assert new.endswith(new_note)
    assert strip_tags(new[:len(new) - len(new_note)]) == key_date
    assert new.count('Note:') == (1 if new_note else 0)


@pytest.mark.django_db
def test_old_indicia_publisher_outside_the_years(client, bulk_change,
                                                 add_issues,
                                                 add_indicia_publisher,
                                                 years_publisher):
    """
    A new indicia publisher whose years hold the key date removes the
    note of the old one: it stands in the Old cell of its row only.
    """
    wide = add_indicia_publisher('Wide Publisher', 1940, 2000)
    [issue] = add_issues(1, '1995-01-00', years_publisher)
    changeset = bulk_change([issue], IssueRevision, indicia_publisher=wide)

    response = page(client, changeset)

    assert cells(response, 'Key Date') == []
    assert cells(response, 'Indicia Publisher') == [(
      "<span class='deleted'>Years Publisher</span>" + note(
        'Indicia publisher', 'Years Publisher', 1995,
        'after its last year 1990'),
      "<span class='added'>Wide Publisher</span>")]


@pytest.mark.django_db
def test_brand_emblem_note_after_the_publisher_note(client, bulk_change,
                                                    add_issues, add_emblem,
                                                    years_publisher):
    """
    Of two brand emblems, the one whose years do not hold the new key
    date has its note in the Key Date row, after the note of the
    indicia publisher.
    """
    emblems = [add_emblem('Inside Emblem', 1980, 2000),
               add_emblem('Outside Emblem', 1980, 1990)]
    [issue] = add_issues(1, '1985-01-00', years_publisher, emblems)
    changeset = bulk_change([issue], IssueRevision, key_date='1995-01-00')

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Key Date')
    notes = note('Indicia publisher', 'Years Publisher', 1995,
                 'after its last year 1990') + \
        note('Brand emblem', 'Outside Emblem', 1995,
             'after its last year 1990')
    assert new.endswith(notes)
    assert new.count('Brand emblem') == 1
    assert strip_tags(new[:-len(notes)]) == '1995-01-00'
    assert 'Note:' not in old


@pytest.mark.django_db
def test_brand_emblem_notes_in_the_order_of_their_names(
        client, bulk_change, add_issues, add_emblem, years_publisher):
    """
    The notes of several brand emblems follow their names, as the Brand
    Emblem cell lists them, whatever the order in which the emblems were
    made.
    """
    # made in the reverse order of their names
    names = ['Zeta Emblem', 'Mid Emblem', 'Alpha Emblem']
    emblems = [add_emblem(name, 1980, 1990) for name in names]
    [issue] = add_issues(1, '1985-01-00', years_publisher, emblems)
    changeset = bulk_change([issue], IssueRevision, key_date='1995-01-00')

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Key Date')
    notes = note('Indicia publisher', 'Years Publisher', 1995,
                 'after its last year 1990') + ''.join(
        note('Brand emblem', name, 1995, 'after its last year 1990')
        for name in sorted(names))
    assert new.endswith(notes)
    assert new.count('Brand emblem') == 3
    assert 'Note:' not in old


@pytest.mark.django_db
def test_rendered_note_is_markup_with_escaped_name(client, bulk_change,
                                                   add_issues,
                                                   add_indicia_publisher):
    """
    On the page the note is markup and the name in it is escaped, as on
    the compare page of one issue.
    """
    ink = add_indicia_publisher('Ink & <Co>', 1980, 1990)
    [issue] = add_issues(1, '1985-01-00', ink)
    changeset = bulk_change([issue], IssueRevision, key_date='1995-01-00')

    content = page(client, changeset).content.decode()

    assert '<br><br>Note: Indicia publisher "Ink &amp; &lt;Co&gt;" used ' \
           'in 1995, after its last year 1990.' in content
    assert '&lt;br' not in content


@pytest.mark.django_db
def test_no_note_for_other_fields(client, bulk_change, add_issues,
                                  add_emblem, years_publisher):
    """
    A price change on an issue stored outside the years of its indicia
    publisher and brand emblem shows no note.
    """
    emblem = add_emblem('Outside Emblem', 1980, 1990)
    [issue] = add_issues(1, '1995-01-00', years_publisher, [emblem])
    changeset = bulk_change([issue], IssueRevision, price='0.25 USD')

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Price')
    assert (strip_tags(old), strip_tags(new)) == ('0.10 USD', '0.25 USD')
    assert 'Note:' not in response.content.decode()


@pytest.mark.django_db
def test_no_query_for_notes_of_other_fields(client, bulk_change, add_issues,
                                            add_emblem, years_publisher):
    """
    A price change needs as many queries on issues that hold an indicia
    publisher and a brand emblem as on issues that hold neither: the
    notes ask for nothing when no key date, indicia publisher or brand
    emblem changed.
    """
    emblem = add_emblem('Outside Emblem', 1980, 1990)
    counts = []
    for publisher, emblems in ((years_publisher, [emblem]), (None, [])):
        issues = add_issues(2, '1995-01-00', publisher, emblems)
        changeset = bulk_change(issues, IssueRevision, price='0.25 USD')
        # The first request also logs in and fills the caches of the site.
        page(client, changeset)
        with CaptureQueriesContext(connection) as queries:
            client.get(reverse('compare', kwargs={'id': changeset.id}))
        counts.append(len(queries))
        changeset.discard(changeset.indexer)

    assert counts[0] == counts[1]


@pytest.mark.django_db
@pytest.mark.parametrize('years, key_date', [
  ((1980, 1990, False, True), '1995-01-00'),
  ((1980, 1990, True, False), '1975-01-00'),
  ((None, None, False, False), '1995-01-00'),
  ((1980, 1990, False, False), '')])
def test_no_note_without_a_certain_year(client, bulk_change, add_issues,
                                        add_indicia_publisher, years,
                                        key_date):
    """
    An uncertain or missing year of the indicia publisher, or a key date
    without a year, gives no note.
    """
    publisher = add_indicia_publisher('Vague Publisher', *years)
    [issue] = add_issues(1, '1985-01-00', publisher)
    changeset = bulk_change([issue], IssueRevision, key_date=key_date)

    response = page(client, changeset)

    [(old, new)] = cells(response, 'Key Date')
    assert strip_tags(new) == key_date
    assert 'Note:' not in response.content.decode()


@pytest.mark.django_db
def test_page_of_a_sequence_change_as_before(client, sequence_change,
                                             approved_stories):
    """The rows of a change of sequences have no note."""
    changeset = sequence_change(approved_stories, genre='Superhero')

    response = page(client, changeset)

    assert [(name, fields) for revision, name, fields
            in response.context['rows']] == \
        [('%s sequence %d' % (story.issue, number),
          [('Genre', "<span class='deleted'>s</span>uperhero",
            "<span class='added'>S</span>uperhero")])
         for number, story in enumerate(approved_stories, start=1)]
    assert 'Note:' not in response.content.decode()


@pytest.mark.django_db
def test_queries_of_notes_do_not_grow_with_the_rows(client, bulk_change,
                                                    add_issues, add_emblem,
                                                    years_publisher):
    """
    A page of three issues with notes needs as many queries as one of
    two.
    """
    emblems = [add_emblem('Inside Emblem', 1980, 2000),
               add_emblem('Outside Emblem', 1980, 1990)]
    issues = add_issues(3, '1985-01-00', years_publisher, emblems)
    counts = []
    for some in (issues[:2], issues):
        changeset = bulk_change(some, IssueRevision, key_date='1995-01-00')
        # The first request also logs in and fills the caches of the site.
        page(client, changeset)
        with CaptureQueriesContext(connection) as queries:
            client.get(reverse('compare', kwargs={'id': changeset.id}))
        counts.append(len(queries))
        changeset.discard(changeset.indexer)

    assert counts[0] == counts[1]
