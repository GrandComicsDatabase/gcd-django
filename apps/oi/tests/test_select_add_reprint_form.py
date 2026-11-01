# -*- coding: utf-8 -*-
"""Tests of the form of the reprint selector: few results, or it says so."""

from html import unescape
import json
import re

import pytest

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import caches
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from apps.gcd.models import Award, Issue, Publisher, Series, Story, StoryType
from apps.gcd.views.pagination import DiggPaginator
from apps.oi.models import SeriesBondRevision
from apps.select.views import FEW_RESULTS
from apps.stddata.models import Country, Language

TOO_MANY_VALUES = [{'id': 'note', 'disabled': True,
                    'text': 'Too many results: write more.'}]
TOO_MANY_NAMED = [{'id': 'note', 'disabled': True,
                   'text': 'Too many results: write more, or choose a '
                           'Publisher or a Series Year.'}]
NO_SERIES = [{'id': 'note', 'disabled': True,
              'text': 'No series with this Issue Number.'}]


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


def search_url(client, select_key):
    """Return the address the page itself asks the form at."""
    return re.search(r'<form id="new-search-form"[^>]*hx-get="([^"]+)"',
                     selector_page(client, select_key)).group(1)


def search(client, select_key, **form):
    """Send the form."""
    return client.get(search_url(client, select_key), form)


def results(response):
    """Return what the buttons of the listed rows choose."""
    return set(re.findall(r'name="object_choice" value="(\w+)"',
                          response.content.decode()))


def story_rows(catalog, *keys):
    """Return what the rows of the stories of the given short names choose."""
    return {f'story_{catalog[key].id}' for key in keys} \
        | {f'issue_{catalog[key].issue_id}' for key in keys}


def stories_listed(response):
    """Return how many stories are listed."""
    return len([choice for choice in results(response)
                if choice.startswith('story_')])


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


def test_reprint_selector_has_only_the_form(client, select_key):
    html = selector_page(client, select_key)
    assert 'class="select_search"' not in html
    assert 'name="search_story"' not in html
    assert 'name="q"' not in html
    assert 'by entering the relevant information' not in html
    assert 'id="new-search-form"' in html


def test_form_has_no_choice_of_what_to_list(client, select_key):
    """The rows have a button for the story and one for the issue."""
    assert 'name="search_object"' not in selector_page(client, select_key)


def test_heading_is_a_heading_when_the_session_cache_is_lost(client,
                                                             select_key):
    """The session comes back from the database, and from JSON a plain text."""
    caches[settings.SESSION_CACHE_ALIAS].clear()
    html = selector_page(client, select_key)
    assert '<h2>Select story/issue' in html
    assert '&lt;h2&gt;' not in html


def test_bond_heading_writes_a_name_as_text(db, client,
                                            any_added_series_bond_rev):
    """The names come from the indexers, and the heading is shown as html."""
    bond = any_added_series_bond_rev
    Series.objects.filter(id=bond.origin_id).update(
      name='<img src=x onerror=alert(1)>')
    indexer = bond.changeset.indexer
    indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(indexer)
    response = client.post(reverse('edit_series_bond', kwargs={'id': bond.id}),
                           {'edit_origin': 'Change'})
    html = selector_page(client, resolve(response.url).kwargs['select_key'])
    assert '<img src=x' not in html
    assert '<h2>Select origin of the bond &lt;img src=x' in html


def test_other_selector_keeps_the_two_searches(client, select_key, catalog):
    """The form finds no series, and a series bond needs to find one."""
    response = client.get(reverse('add_series_bond',
                                  kwargs={'series_id': catalog['xmen91'].id}))
    html = selector_page(client, resolve(response.url).kwargs['select_key'])
    assert 'class="select_search"' in html
    assert 'name="search_series"' in html
    assert 'name="q"' in html


def bond_selector(client, catalog):
    """Follow the link to add a series bond and return the selector key."""
    response = client.get(reverse('add_series_bond',
                                  kwargs={'series_id': catalog['xmen91'].id}))
    return resolve(response.url).kwargs['select_key']


def test_form_is_only_where_stories_and_issues_can_be_chosen(
        client, select_key, catalog):
    """Its rows choose one or the other, whatever the selector takes."""
    assert 'id="new-search-form"' in selector_page(client, select_key)
    html = selector_page(client, bond_selector(client, catalog))
    assert 'id="new-search-form"' not in html
    response = client.get(reverse('edit_two_issues',
                                  kwargs={'issue_id': catalog['a'].id}))
    html = selector_page(client, resolve(response.url).kwargs['select_key'])
    assert 'id="new-search-form"' not in html


def test_award_selector_keeps_the_form(client, select_key, any_edit_story_rev):
    """An award goes to a story or to an issue, or to a series."""
    indexer = any_edit_story_rev.changeset.indexer.indexer
    indexer.max_reservations = 5
    indexer.save()
    award = Award.objects.create(name='Any award')
    response = client.get(reverse('select_award_recipient',
                                  kwargs={'award_id': award.id}))
    html = selector_page(client, resolve(response.url).kwargs['select_key'])
    assert 'id="new-search-form"' in html


def test_selector_refuses_what_it_does_not_take(client, select_key, catalog):
    """A series bond would save the issue with the id of the story."""
    bonds = SeriesBondRevision.objects.count()
    response = client.post(
      reverse('select_object',
              kwargs={'select_key': bond_selector(client, catalog)}),
      {'search_select': '1',
       'object_choice': f'story_{catalog["a_story"].id}'})
    assert response.status_code == 400
    assert SeriesBondRevision.objects.count() == bonds


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
    """The name equal to the text first, then the alphabetical order."""
    for number in range(extra):
        Publisher.objects.create(name='Marvel %02d' % number,
                                 country=catalog['country'], year_began=2000)
    values = menu(client, select_key, 'publisher_auto', 'marvel')
    if too_many:
        assert labels(values[:-1]) == ['Marvel'] + [
          'Marvel %02d' % number for number in range(FEW_RESULTS - 1)]
        assert values[-1:] == TOO_MANY_VALUES
    else:
        assert len(values) == FEW_RESULTS


def test_opened_publisher_menu_lists_few_values_too(client, select_key,
                                                    catalog):
    """With no text to go by, the first values would be any values."""
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
    assert len(values) == FEW_RESULTS + 1
    assert values[-1:] == TOO_MANY_VALUES


def test_publisher_is_found_by_its_id_among_too_many(client, select_key,
                                                     catalog):
    """Names that contain the id must not push the publisher off the list."""
    wanted = catalog['marvel_uk']
    for number in range(FEW_RESULTS + 1):
        Publisher.objects.create(name='Some %d' % wanted.id,
                                 country=catalog['country'], year_began=2000)
    values = menu(client, select_key, 'publisher_auto', str(wanted.id))
    assert values[0]['id'] == str(wanted.id)
    assert len(values) == FEW_RESULTS + 1
    assert values[-1:] == TOO_MANY_VALUES


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
    """The publisher alone narrows it, and so does a year with a publisher."""
    assert [value['id'] for value in menu(
      client, select_key, 'series_auto', 'xmen',
      publisher=str(catalog['marvel_uk'].id))] == [str(catalog['xmen_uk'].id)]
    assert [value['id'] for value in menu(
      client, select_key, 'series_auto', '',
      publisher=str(catalog['marvel'].id),
      series_year='2009')] == [str(catalog['forever'].id)]


def test_series_menu_leaves_out_deleted_series(client, select_key, catalog):
    """A deleted X-Men has the same name as the two that can be chosen."""
    ids = [value['id'] for value in menu(client, select_key, 'series_auto',
                                         'xmen')]
    assert str(catalog['deleted'].id) not in ids


@pytest.mark.parametrize('name', [
  'X\u2013Men', 'X\u2014Men', 'X\u2015Men', 'X/Men', 'X\u2019Men',
  'X\u2018Men',
])
def test_series_menu_leaves_out_the_other_separators(client, select_key,
                                                     catalog, name):
    """Long dashes, slashes and curly apostrophes must not hide a name."""
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
    """The two series called X-Men first, then the others up to the limit."""
    for number in range(extra):
        another_series(catalog, 'X-Men %d' % number)
    values = menu(client, select_key, 'series_auto', 'xmen')
    if too_many:
        assert [value['id'] for value in values[:2]] == [
          str(catalog['xmen91'].id), str(catalog['xmen_uk'].id)]
        assert len(values) == FEW_RESULTS + 1
        assert values[-1:] == TOO_MANY_VALUES
    else:
        assert len(values) == FEW_RESULTS


def test_part_of_a_name_lists_the_first_series_among_too_many(
        client, select_key, catalog):
    """As with nathan ne of Sergio Bonelli Editore: 26 series, 20 listed."""
    for number in reversed(range(FEW_RESULTS + 1)):
        another_series(catalog, 'Nathan Never %02d' % number)
    values = menu(client, select_key, 'series_auto', 'nathan ne',
                  publisher=str(catalog['marvel'].id))
    assert labels(values[:-1]) == [
      'Nathan Never %02d (Marvel, 2000 series) - XA, 0 issues' % number
      for number in range(FEW_RESULTS)]
    assert values[-1:] == TOO_MANY_VALUES


def test_opened_series_menu_only_says_when_values_are_too_many(
        client, select_key, catalog):
    """With no text to go by, the first values would be any values."""
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'Some %d' % number)
    assert menu(client, select_key, 'series_auto') == TOO_MANY_VALUES


def test_series_with_too_many_longer_names_can_still_be_chosen(
        client, select_key, catalog):
    """Alphabetically they could fall out, as with Le grandi storie."""
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'A X-Men %d' % number, year_began=2010)
    wanted = another_series(catalog, 'X-Men', year_began=2010)
    values = menu(client, select_key, 'series_auto', 'X-Men',
                  publisher=str(catalog['marvel'].id), series_year='2010')
    assert values[0]['id'] == str(wanted.id)
    assert len(values) == FEW_RESULTS + 1
    assert values[-1:] == TOO_MANY_VALUES


def test_too_many_series_with_the_same_name_ask_for_publisher_or_year(
        client, select_key, catalog):
    """Writing more cannot reach them: as with Batman in the catalog."""
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'Klassiker', year_began=1950 + number)
    values = menu(client, select_key, 'series_auto', 'klassiker')
    assert len(values) == FEW_RESULTS + 1
    assert values[-1:] == TOO_MANY_NAMED
    wanted = another_series(catalog, 'Klassiker', year_began=2020)
    values = menu(client, select_key, 'series_auto', 'klassiker',
                  series_year='2020')
    assert [value['id'] for value in values] == [str(wanted.id)]


def test_series_is_found_by_its_id(client, select_key, catalog):
    """Writing the id of a series in the menu lists only that series."""
    wanted = catalog['forever']
    assert [value['id'] for value in menu(client, select_key, 'series_auto',
                                          str(wanted.id))] == [str(wanted.id)]


def test_series_is_found_by_its_id_among_too_many(client, select_key, catalog):
    """Names that contain the id must not push the series off the list."""
    wanted = catalog['forever']
    for number in range(FEW_RESULTS + 1):
        another_series(catalog, 'Volume %d' % wanted.id)
    values = menu(client, select_key, 'series_auto', str(wanted.id))
    assert values[0]['id'] == str(wanted.id)
    assert len(values) == FEW_RESULTS + 1
    assert values[-1:] == TOO_MANY_VALUES


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


def test_menus_find_a_key_inside_the_name(client, select_key, catalog):
    """The text is looked for at any point of the name."""
    assert labels(menu(client, select_key, 'publisher_auto', 'arv')) == [
      'Marvel', 'Marvel UK']
    assert [value['id'] for value in menu(client, select_key, 'series_auto',
                                          'forever')] \
        == [str(catalog['forever'].id)]


@pytest.mark.parametrize('forward', [
    {'publisher': 'marvel'}, {'series_year': '1991'}])
@pytest.mark.parametrize('number', ['2', '10', '1'])
def test_number_narrows_the_series_menu(client, select_key, catalog, forward,
                                        number):
    """Going on after the number too: X-Men of 1991 has no plain 1."""
    if 'publisher' in forward:
        forward = {'publisher': str(catalog['marvel'].id)}
    values = menu(client, select_key, 'series_auto', 'xmen',
                  issue_number=number, **forward)
    assert [value['id'] for value in values] == [str(catalog['xmen91'].id)]


def test_number_lists_what_the_text_alone_finds_too_many(client, select_key,
                                                         catalog):
    """As with DC, 2014, batm and 2: 49 series, 16 of them with that number."""
    wanted = None
    for number in range(FEW_RESULTS + 1):
        wanted = another_series(catalog, 'X-Men %d' % number, year_began=2014)
    Issue.objects.create(series=wanted, number='2', sort_code=1)
    forward = {'publisher': str(catalog['marvel'].id), 'series_year': '2014'}
    assert menu(client, select_key, 'series_auto', 'xmen', **forward)[-1:] \
        == TOO_MANY_VALUES
    values = menu(client, select_key, 'series_auto', 'xmen', issue_number='2',
                  **forward)
    assert [value['id'] for value in values] == [str(wanted.id)]


def test_number_alone_does_not_narrow_the_series_menu(client, select_key):
    """Among all the series it would take seconds at each key."""
    assert len(menu(client, select_key, 'series_auto', 'xmen',
                    issue_number='2')) == 3


def test_number_no_series_has_is_said_by_the_series_menu(client, select_key,
                                                         catalog):
    assert menu(client, select_key, 'series_auto', 'xmen', issue_number='999',
                publisher=str(catalog['marvel'].id)) == NO_SERIES


def test_deleted_issue_does_not_narrow_the_series_menu(client, select_key,
                                                       catalog):
    Issue.objects.create(series=catalog['xmen91'], number='7', sort_code=8,
                         deleted=True)
    assert menu(client, select_key, 'series_auto', 'xmen', issue_number='7',
                publisher=str(catalog['marvel'].id)) == NO_SERIES


# the results


def test_chosen_series_is_not_emptied_by_publisher_or_year(client, select_key,
                                                           catalog):
    """They can disagree with it, as with Batman of 2024 and the year 2014."""
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      publisher_auto=catalog['marvel_uk'].id,
                      series_year_auto=2014, issue_number='2')
    assert results(response) == story_rows(catalog, 'second_cover',
                                           'second_story')


def test_number_goes_on_inside_a_series(client, select_key, catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='1')
    assert results(response) == story_rows(catalog, 'a_cover', 'a_story',
                                           'b_cover', 'b_story')


def test_number_going_on_ignores_case_like_the_exact_one(
        client, select_key, catalog):
    issue = Issue.objects.create(series=catalog['xmen91'], sort_code=9,
                                 number='April 1968 [2]')
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='april 1968')
    assert results(response) == {f'issue_{issue.id}'}


def test_number_does_not_go_on_into_longer_numbers(client, select_key,
                                                   catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='1')
    assert f'issue_{catalog["tenth"].id}' not in results(response)


def test_number_alone_is_exact(client, select_key, catalog):
    response = search(client, select_key, issue_number='1')
    assert results(response) == story_rows(catalog, 'uk_cover', 'uk_story')


def test_number_goes_on_with_a_publisher_or_a_year(client, select_key,
                                                   catalog):
    expected = story_rows(catalog, 'a_cover', 'a_story', 'b_cover', 'b_story')
    assert results(search(client, select_key, issue_number='1',
                          publisher_auto=catalog['marvel'].id)) == expected
    assert results(search(client, select_key, issue_number='1',
                          series_year_auto=1991)) == expected


def test_story_rows_have_the_buttons_of_the_story_and_of_the_issue(
        client, select_key, catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2')
    html = response.content.decode()
    assert html.count('Select This Story') == 2
    assert html.count('Select This Issue') == 2


def test_issue_without_sequences_is_listed_with_its_button(client, select_key,
                                                           catalog):
    """Most issues are so, and the stories have no row for them."""
    issue = Issue.objects.create(series=catalog['xmen91'], sort_code=9,
                                 number='1 [Cover C]')
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='1')
    html = response.content.decode()
    assert results(response) == story_rows(
      catalog, 'a_cover', 'a_story', 'b_cover', 'b_story') \
        | {f'issue_{issue.id}'}
    assert html.count('Select This Story') == 4
    assert html.count('Select This Issue') == 5
    assert html.index('Select This Story') \
        < html.index(f'value="issue_{issue.id}"')


def test_only_issues_without_sequences_are_listed(client, select_key, catalog):
    issue = Issue.objects.create(series=catalog['forever'], number='1',
                                 sort_code=1)
    response = search(client, select_key, series_auto=catalog['forever'].id)
    assert results(response) == {f'issue_{issue.id}'}
    assert 'Select This Story' not in response.content.decode()


def test_nothing_found_says_so(client, select_key, catalog):
    response = search(client, select_key, series_auto=catalog['forever'].id)
    assert '0 to 0 of 0 objects' in ' '.join(response.content.decode().split())


@pytest.mark.parametrize('extra, too_many', [(FEW_RESULTS - 8, False),
                                             (FEW_RESULTS - 7, True)])
def test_stories_and_issues_count_together(client, select_key, catalog, extra,
                                           too_many):
    """A series of 8 stories must not hide the issues without sequences."""
    for number in range(extra):
        Issue.objects.create(series=catalog['xmen91'], number=f'{number + 20}',
                             sort_code=number + 20)
    response = search(client, select_key, series_auto=catalog['xmen91'].id)
    if too_many:
        assert response.content \
          == b'<p>Too many results: write the Issue Number.</p>'
    else:
        assert stories_listed(response) == 8
        assert len(results(response)) == FEW_RESULTS + 4


def test_issues_are_not_read_with_too_many_stories(client, select_key,
                                                   catalog):
    """Among all the issues of a publisher they take seconds."""
    url = search_url(client, select_key)
    with CaptureQueriesContext(connection) as few:
        client.get(url, {'publisher_auto': catalog['marvel'].id})
    assert any('NOT EXISTS' in query['sql'] for query in few)
    many_stories(catalog, 'second', FEW_RESULTS)
    with CaptureQueriesContext(connection) as many:
        client.get(url, {'publisher_auto': catalog['marvel'].id})
    assert not any('NOT EXISTS' in query['sql'] for query in many)


def test_few_results_are_listed_without_a_number(client, select_key, catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id)
    assert stories_listed(response) == 8


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
    assert stories_listed(response) == FEW_RESULTS


def test_series_and_number_always_list(client, select_key, catalog):
    """Nothing is left to narrow down: the page must not stop here."""
    many_stories(catalog, 'second', FEW_RESULTS + 5)
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2')
    assert stories_listed(response) == FEW_RESULTS + 7


# the pages of a table


def page_links(response):
    """Return the addresses of the links to other pages, by their page."""
    return {int(link.rsplit('=', 1)[1]): link for link in (
      unescape(found) for found in re.findall(
        r'<a [^>]*href="([^"]*page=\d+)"', response.content.decode()))}


def long_table(client, select_key, catalog):
    """Return the first page of the 102 stories of an issue."""
    many_stories(catalog, 'second', 100)
    return search(client, select_key, series_auto=catalog['xmen91'].id,
                  issue_number='2', publisher_auto='', series_year_auto='')


def test_short_table_has_no_links_to_pages(client, select_key, catalog):
    """A table that fits in one page shows no bar."""
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2')
    assert not page_links(response)
    assert 'hx-boost' not in response.content.decode()


def test_links_of_a_long_table_ask_the_search_for_the_same_form(
        client, select_key, catalog):
    response = long_table(client, select_key, catalog)
    link = page_links(response)[2]
    assert link.startswith(search_url(client, select_key) + '?')
    assert f'series_auto={catalog["xmen91"].id}' in link
    assert 'issue_number=2' in link


def test_box_of_a_long_table_asks_the_search_for_the_same_form(
        client, select_key, catalog):
    html = long_table(client, select_key, catalog).content.decode()
    box = re.search(r'<form method="GET" action="([^"]+)">.*?</form>', html,
                    re.DOTALL)
    assert box.group(1) == search_url(client, select_key)
    assert 'name="issue_number" value="2"' in box.group()


def test_pages_of_a_long_table_list_each_story_once(client, select_key,
                                                    catalog):
    """The two pages together hold every story, and the links go both ways."""
    response = long_table(client, select_key, catalog)
    first = results(response)
    assert stories_listed(response) == 100
    second = client.get(page_links(response)[2],
                        headers={'HX-Target': 'story-results'})
    assert stories_listed(second) == 2
    stories = Story.objects.filter(issue=catalog['second'], deleted=False)
    assert {choice for choice in first | results(second)
            if choice.startswith('story_')} \
        == {f'story_{story.id}' for story in stories}
    assert page_links(second)[1] == page_links(response)[2].replace(
      'page=2', 'page=1')


def test_pages_of_one_table_leave_the_other_alone(client, select_key, catalog):
    """As with Il Giornalino 3, whose 484 stories hid the issues."""
    many_stories(catalog, 'second', 100)
    issues = [Issue.objects.create(series=catalog['xmen91'], sort_code=9 + n,
                                   number=f'2 [{n}]') for n in range(101)]
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2')
    html = response.content.decode()
    assert 'id="story-results"' in html and 'id="issue-results"' in html
    link = page_links(response)[2]

    stories = client.get(link, headers={'HX-Target': 'story-results'})
    html = stories.content.decode()
    assert 'id="story-results"' in html and 'id="issue-results"' not in html
    assert stories_listed(stories) == 2

    others = client.get(link, headers={'HX-Target': 'issue-results'})
    html = others.content.decode()
    assert 'id="issue-results"' in html and 'id="story-results"' not in html
    assert results(others) == {f'issue_{issues[100].id}'}


def test_link_to_a_page_is_as_it_was_elsewhere(db):
    """Without page_url the shared bar writes its links as before."""
    html = render_to_string(
      'gcd/bits/tw_pagination_bar.html',
      {'page': DiggPaginator(range(200), 100, body=7, padding=2,
                             tail=1).page(1),
       'query_string': 'a=b'})
    assert 'href="?a=b&amp;page=2"' in html
    assert '<form method="GET">' in html


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
                      issue_number='1')
    assert results(response) == {f'issue_{issue.id}'}


def test_year_that_is_no_number_is_left_out(client, select_key, catalog):
    response = search(client, select_key, series_year_auto='abc',
                      issue_number='1')
    assert results(response) == story_rows(catalog, 'uk_cover', 'uk_story')
