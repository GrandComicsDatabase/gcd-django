# -*- coding: utf-8 -*-
"""Tests of the form of the reprint selector: few results, or it says so."""

import json
import re

import pytest

from django.contrib.auth.models import Permission
from django.urls import resolve, reverse

from apps.gcd.models import Issue, Publisher, Series, Story, StoryType
from apps.select.views import FEW_RESULTS
from apps.stddata.models import Country, Language

TOO_MANY_VALUES = [{'id': 'too_many', 'disabled': True,
                    'text': 'Too many results: write more.'}]
TOO_MANY_NAMED = [{'id': 'too_many', 'disabled': True,
                   'text': 'Too many results: write more, or choose a '
                           'Publisher or a Series Year.'}]


@pytest.fixture
def catalog(db):
    """
    Return a small catalog by short names: X-Men of 1991 from Marvel with its
    issues and sequences, X-Men of 1992 from Marvel UK, X-Men Forever, a series
    called X and a deleted X-Men.
    """
    country = Country.objects.get_or_create(
      code='xa', defaults={'name': 'Search country'})[0]
    language = Language.objects.get_or_create(
      code='xa', defaults={'name': 'Search language'})[0]
    marvel = Publisher.objects.create(name='Marvel', country=country,
                                      year_began=1939)
    marvel_uk = Publisher.objects.create(name='Marvel UK', country=country,
                                         year_began=1972)

    def series(name, publisher, year_began, issue_count, **extra):
        """Create and return a series."""
        return Series.objects.create(
          name=name, sort_name=name, publisher=publisher, country=country,
          language=language, year_began=year_began, issue_count=issue_count,
          **extra)

    found = {
      'marvel': marvel, 'marvel_uk': marvel_uk,
      'xmen91': series('X-Men', marvel, 1991, 118),
      'xmen_uk': series('X-Men', marvel_uk, 1992, 1),
      'forever': series('X-Men Forever', marvel, 2009, 24),
      'x': series('X', marvel, 2013, 28),
      'deleted': series('X-Men', marvel, 1991, 0, deleted=True),
    }
    cover = StoryType.objects.get(name='cover')
    comic_story = StoryType.objects.get(name='comic story')

    def issue(key, series_key, number, sort_code):
        """Create an issue with a cover and a story under a short name."""
        found[key] = Issue.objects.create(series=found[series_key],
                                          number=number, sort_code=sort_code)
        found[key + '_cover'] = Story.objects.create(
          issue=found[key], sequence_number=0, type=cover)
        found[key + '_story'] = Story.objects.create(
          issue=found[key], sequence_number=1, type=comic_story)

    issue('a', 'xmen91', '1 [Cover A]', 1)
    issue('b', 'xmen91', '1 [Cover B]', 2)
    issue('second', 'xmen91', '2', 3)
    issue('tenth', 'xmen91', '10', 4)
    issue('uk', 'xmen_uk', '1', 1)
    found['language'], found['country'] = language, country
    return found


def another_series(catalog, name, year_began=2000, publisher='marvel'):
    """Create a series of the catalog with the given name."""
    return Series.objects.create(
      name=name, sort_name=name, publisher=catalog[publisher],
      country=catalog['country'], language=catalog['language'],
      year_began=year_began)


@pytest.fixture
def select_key(client, catalog, any_edit_story_rev):
    """Follow Add Reprint of a sequence and return the selector key."""
    indexer = any_edit_story_rev.changeset.indexer
    indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(indexer)
    response = client.get(reverse(
      'add_story_reprint',
      kwargs={'story_id': any_edit_story_rev.id,
              'changeset_id': any_edit_story_rev.changeset_id}))
    return resolve(response.url).kwargs['select_key']


def selector_page(client, select_key):
    """Return the html of the selector page."""
    return client.get(reverse('select_object',
                              kwargs={'select_key': select_key})
                      ).content.decode()


def search(client, select_key, **form):
    """Send the form, asked where the page itself asks it."""
    url = re.search(r'<form id="new-search-form"[^>]*hx-get="([^"]+)"',
                    selector_page(client, select_key)).group(1)
    return client.get(url, form)


def results(response):
    """Return the ids of the objects listed by the form."""
    return {row.record.id for row in response.context['table'].rows}


def menu_url(client, select_key, field):
    """Return the address of the menu of a field, read from the page."""
    tag = re.search(r'<select[^>]*name="%s"[^>]*>' % field,
                    selector_page(client, select_key)).group()
    return re.search(r'data-autocomplete-light-url="([^"]+)"', tag).group(1)


def menu(client, select_key, field, text='', **forward):
    """Return the values the menu of a field lists for the typed text."""
    return client.get(menu_url(client, select_key, field),
                      {'q': text, 'forward': json.dumps(forward)}
                      ).json()['results']


def labels(values):
    """Return the texts of the values of a menu."""
    return [value['text'] for value in values]


# the form


def test_form_is_sent_whatever_the_limits_and_without_number(client,
                                                             select_key):
    """A browser check of the form would stop it without a word."""
    html = selector_page(client, select_key)
    assert re.search(r'<form id="new-search-form"[^>]*\bnovalidate\b', html)
    number = re.search(r'<input[^>]*name="issue_number"[^>]*>', html).group()
    assert 'required' not in number
    assert 'htmx:responseError' in html


def test_form_needs_the_right_to_edit(client, catalog, any_edit_story_rev):
    """A lost session is an error the page writes, not a login page in it."""
    response = client.get(reverse('select_object_search_htmx',
                                  kwargs={'select_key': 'any'}),
                          {'issue_number': '1'})
    assert response.status_code == 403


def test_empty_form_lists_nothing(client, select_key):
    response = search(client, select_key, publisher_auto='', series_auto='',
                      series_year_auto='', issue_number='')
    assert response.status_code == 200
    assert response.content == b''


# the menus


def test_publisher_menu_lists_few_values(client, select_key):
    assert labels(menu(client, select_key, 'publisher_auto', 'marvel')) \
      == ['Marvel', 'Marvel UK']


@pytest.mark.parametrize('extra, too_many', [(FEW_RESULTS - 2, False),
                                             (FEW_RESULTS - 1, True)])
def test_publisher_menu_says_when_values_are_too_many(
        client, select_key, catalog, extra, too_many):
    for number in range(extra):
        Publisher.objects.create(name='Marvel %d' % number,
                                 country=catalog['country'], year_began=2000)
    values = menu(client, select_key, 'publisher_auto', 'marvel')
    if too_many:
        assert labels(values[:-1]) == ['Marvel']
        assert values[-1:] == TOO_MANY_VALUES
    else:
        assert len(values) == FEW_RESULTS


def test_opened_publisher_menu_lists_few_values_too(client, select_key,
                                                    catalog):
    for number in range(FEW_RESULTS):
        Publisher.objects.create(name='Some %d' % number,
                                 country=catalog['country'], year_began=2000)
    assert menu(client, select_key, 'publisher_auto') == TOO_MANY_VALUES


def test_publisher_with_too_many_longer_names_can_still_be_chosen(
        client, select_key, catalog):
    """Writing more would leave it out, as with DC in the catalog."""
    for number in range(FEW_RESULTS + 1):
        Publisher.objects.create(name='DC %d' % number,
                                 country=catalog['country'], year_began=2000)
    wanted = Publisher.objects.create(name='DC', country=catalog['country'],
                                      year_began=1935)
    values = menu(client, select_key, 'publisher_auto', ' dc ')
    assert values[0]['id'] == str(wanted.id)
    assert values[1:] == TOO_MANY_VALUES


def test_publisher_is_found_by_its_id_among_too_many(client, select_key,
                                                     catalog):
    wanted = catalog['marvel_uk']
    for number in range(FEW_RESULTS + 1):
        Publisher.objects.create(name='Some %d' % wanted.id,
                                 country=catalog['country'], year_began=2000)
    values = menu(client, select_key, 'publisher_auto', str(wanted.id))
    assert values[0]['id'] == str(wanted.id)
    assert values[1:] == TOO_MANY_VALUES


def test_series_menu_compares_names_without_separators(client, select_key):
    assert labels(menu(client, select_key, 'series_auto', 'xmen')) == [
      'X-Men (Marvel, 1991 series) - XA, 118 issues',
      'X-Men (Marvel UK, 1992 series) - XA, 1 issue',
      'X-Men Forever (Marvel, 2009 series) - XA, 24 issues']


def test_series_menu_tells_twin_series_apart_by_binding(client, select_key,
                                                        catalog):
    """Two series of the catalog differ only in this."""
    for binding in ('Softcover', 'Hardcover'):
        twin = another_series(catalog, 'Klassiker', year_began=2016)
        twin.binding = binding
        twin.save()
    assert labels(menu(client, select_key, 'series_auto', 'klassiker')) == [
      'Klassiker (Marvel, 2016 series) - XA, 0 issues, Softcover',
      'Klassiker (Marvel, 2016 series) - XA, 0 issues, Hardcover']


def test_series_menu_lists_the_equal_name_first(client, select_key, catalog):
    another_series(catalog, 'A story of X-Men')
    first = labels(menu(client, select_key, 'series_auto', 'x men'))[0]
    assert first.startswith('X-Men (')


def test_series_menu_is_narrowed_by_publisher_and_year(
        client, select_key, catalog):
    assert [value['id'] for value in menu(
      client, select_key, 'series_auto', 'xmen',
      publisher=str(catalog['marvel_uk'].id))] == [str(catalog['xmen_uk'].id)]
    assert [value['id'] for value in menu(
      client, select_key, 'series_auto', '',
      publisher=str(catalog['marvel'].id),
      series_year='2009')] == [str(catalog['forever'].id)]


def test_series_menu_leaves_out_deleted_series(client, select_key, catalog):
    ids = [value['id'] for value in menu(client, select_key, 'series_auto',
                                         'xmen')]
    assert str(catalog['deleted'].id) not in ids


@pytest.mark.parametrize('name', [
  'X\u2013Men', 'X\u2014Men', 'X\u2015Men', 'X/Men', 'X\u2019Men',
  'X\u2018Men',
])
def test_series_menu_leaves_out_the_other_separators(client, select_key,
                                                     catalog, name):
    wanted = another_series(catalog, name)
    assert str(wanted.id) in [value['id'] for value in menu(
      client, select_key, 'series_auto', 'xmen')]


def test_series_menu_lists_what_contains_a_short_text(client, select_key,
                                                      catalog):
    assert labels(menu(client, select_key, 'series_auto', 'xm')) == [
      'X-Men (Marvel, 1991 series) - XA, 118 issues',
      'X-Men (Marvel UK, 1992 series) - XA, 1 issue',
      'X-Men Forever (Marvel, 2009 series) - XA, 24 issues']


def test_series_menu_lists_the_whole_short_name_first(client, select_key,
                                                      catalog):
    values = menu(client, select_key, 'series_auto', 'x')
    assert values[0]['id'] == str(catalog['x'].id)
    assert len(values) == 4


@pytest.mark.parametrize('extra, too_many', [(FEW_RESULTS - 3, False),
                                             (FEW_RESULTS - 2, True)])
def test_series_menu_says_when_values_are_too_many(
        client, select_key, catalog, extra, too_many):
    for number in range(extra):
        another_series(catalog, 'X-Men %d' % number)
    values = menu(client, select_key, 'series_auto', 'xmen')
    if too_many:
        assert [value['id'] for value in values[:-1]] == [
          str(catalog['xmen91'].id), str(catalog['xmen_uk'].id)]
        assert values[-1:] == TOO_MANY_VALUES
    else:
        assert len(values) == FEW_RESULTS


def test_series_with_too_many_longer_names_can_still_be_chosen(
        client, select_key, catalog):
    """Writing more would leave it out, as with X-Men of Marvel of 2010."""
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'X-Men %d' % number, year_began=2010)
    wanted = another_series(catalog, 'X-Men', year_began=2010)
    values = menu(client, select_key, 'series_auto', 'X-Men',
                  publisher=str(catalog['marvel'].id), series_year='2010')
    assert values[0]['id'] == str(wanted.id)
    assert values[1:] == TOO_MANY_VALUES


def test_too_many_series_with_the_same_name_ask_for_publisher_or_year(
        client, select_key, catalog):
    """Writing more cannot reach them: as with Batman in the catalog."""
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'Klassiker', year_began=1950 + number)
    values = menu(client, select_key, 'series_auto', 'klassiker')
    assert values == TOO_MANY_NAMED
    wanted = another_series(catalog, 'Klassiker', year_began=2020)
    values = menu(client, select_key, 'series_auto', 'klassiker',
                  series_year='2020')
    assert [value['id'] for value in values] == [str(wanted.id)]


def test_series_is_found_by_its_id(client, select_key, catalog):
    wanted = catalog['forever']
    assert [value['id'] for value in menu(client, select_key, 'series_auto',
                                          str(wanted.id))] == [str(wanted.id)]


def test_series_is_found_by_its_id_among_too_many(client, select_key, catalog):
    wanted = catalog['forever']
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'Volume %d' % wanted.id)
    values = menu(client, select_key, 'series_auto', str(wanted.id))
    assert values[0]['id'] == str(wanted.id)
    assert values[1:] == TOO_MANY_VALUES


def test_series_id_must_agree_with_publisher_and_year(client, select_key,
                                                      catalog):
    assert menu(client, select_key, 'series_auto', str(catalog['forever'].id),
                publisher=str(catalog['marvel_uk'].id)) == []


def test_deleted_series_is_not_named_by_its_id(client, select_key, catalog):
    assert menu(client, select_key, 'series_auto',
                str(catalog['deleted'].id)) == []


@pytest.mark.parametrize('field', ['publisher_auto', 'series_auto'])
def test_menus_bear_an_id_too_long_for_the_database(client, select_key, field):
    assert menu(client, select_key, field, '9' * 40) == []


def test_series_menu_with_a_mistaken_year_lists_nothing_wrong(
        client, select_key):
    assert menu(client, select_key, 'series_auto', 'xmen', series_year='abc')


# the results


def test_number_goes_on_inside_a_series(client, select_key, catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='1')
    assert results(response) == {
      catalog[key].id for key in ('a_cover', 'a_story', 'b_cover', 'b_story')}


def test_number_going_on_ignores_case_like_the_exact_one(
        client, select_key, catalog):
    issue = Issue.objects.create(series=catalog['xmen91'], sort_code=9,
                                 number='April 1968 [2]')
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='april 1968', search_object='issue')
    assert results(response) == {issue.id}


def test_number_does_not_go_on_into_longer_numbers(client, select_key,
                                                   catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='1', search_object='issue')
    assert catalog['tenth'].id not in results(response)


def test_number_is_exact_without_a_series(client, select_key, catalog):
    response = search(client, select_key, issue_number='1')
    assert results(response) == {catalog['uk_cover'].id,
                                 catalog['uk_story'].id}


@pytest.mark.parametrize('search_object, expected', [
    ('cover', {'a_cover', 'b_cover'}),
    ('issue', {'a', 'b'}),
])
def test_form_finds_covers_and_issues(client, select_key, catalog,
                                      search_object, expected):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='1', search_object=search_object)
    assert results(response) == {catalog[key].id for key in expected}


def test_few_results_are_listed_without_a_number(client, select_key, catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id)
    assert len(results(response)) == 8


def many_stories(catalog, number, how_many):
    """Add stories to the issue of the given short name."""
    story_type = StoryType.objects.get(name='comic story')
    for sequence_number in range(how_many):
        Story.objects.create(issue=catalog[number], type=story_type,
                             sequence_number=sequence_number + 2)


def test_too_many_results_ask_for_the_number(client, select_key, catalog):
    many_stories(catalog, 'second', FEW_RESULTS)
    response = search(client, select_key, series_auto=catalog['xmen91'].id)
    expected = b'<p>Too many results: write the Issue Number.</p>'
    assert response.content == expected


def test_too_many_results_ask_for_the_series(client, select_key, catalog):
    many_stories(catalog, 'second', FEW_RESULTS)
    response = search(client, select_key, publisher_auto=catalog['marvel'].id)
    assert response.content == b'<p>Too many results: choose a Series.</p>'


def test_exactly_the_most_results_are_listed(client, select_key, catalog):
    many_stories(catalog, 'second', FEW_RESULTS - 8)
    response = search(client, select_key, series_auto=catalog['xmen91'].id)
    assert len(results(response)) == FEW_RESULTS


def test_series_and_number_always_list(client, select_key, catalog):
    """Nothing is left to narrow down: the page must not stop here."""
    many_stories(catalog, 'second', FEW_RESULTS + 5)
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2')
    assert len(results(response)) == FEW_RESULTS + 7


@pytest.mark.parametrize('year', [0, 1682, 2027, 20005])
def test_year_outside_the_limits_of_the_form_still_narrows(
        client, select_key, catalog, year):
    """The catalog has such series, and they must be reachable."""
    odd = another_series(catalog, 'Odd year', year_began=year)
    assert [value['id'] for value in menu(
      client, select_key, 'series_auto', 'odd year',
      series_year=str(year))] == [str(odd.id)]
    issue = Issue.objects.create(series=odd, number='1', sort_code=1)
    response = search(client, select_key, series_year_auto=year,
                      issue_number='1', search_object='issue')
    assert results(response) == {issue.id}


def test_year_that_is_no_number_is_left_out(client, select_key, catalog):
    response = search(client, select_key, series_year_auto='abc',
                      issue_number='1', search_object='issue')
    assert results(response) == {catalog['uk'].id}
