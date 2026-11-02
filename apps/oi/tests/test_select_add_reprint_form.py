# -*- coding: utf-8 -*-
"""Tests of the form of the reprint selector: few results, or it says so."""

from html import unescape
import json
import re
from unittest.mock import patch

import pytest

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import caches
from django.db import connection
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from apps.gcd.models import Award, Brand, Issue, Publisher, Series, Story, \
                            StoryType
from apps.gcd.views.pagination import DiggPaginator
from apps.oi.models import ReprintRevision, SeriesBondRevision
from apps.select.views import FEW_RESULTS
from apps.stddata.models import Country, Language

TOO_MANY_VALUES = [{'id': 'note', 'disabled': True,
                    'text': 'Too many results: write more.'}]
TOO_MANY_NAMED = [{'id': 'note', 'disabled': True,
                   'text': 'Too many results: write more, or choose a '
                           'Publisher or a Series Year.'}]
NO_SERIES = [{'id': 'note', 'disabled': True,
              'text': 'No series with this Issue Number.'}]
NO_SERIES_NAMED = [{'id': 'note', 'disabled': True,
                    'text': 'No series with this name and this Issue Number.'}]
ASK_SERIES = b'<p>Too many results: choose a Series.</p>'
ASK_NUMBER = b'<p>Too many results: write the Issue Number.</p>'
SEARCH_ON_OPEN = 'pageshow[!event.persisted] from:window, change delay:500ms'


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
    found['xmen91'].set_first_last_issues()
    found['xmen_uk'].set_first_last_issues()
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


def cover_rows(catalog, *keys):
    """Return what the rows of the covers of the given issues choose."""
    return {f'cover_{catalog[key + "_cover"].id}' for key in keys} \
        | {f'issue_{catalog[key].id}' for key in keys}


def radio_buttons(html):
    """Return the choices of the radio buttons of the form, and which is on."""
    form = re.search(r'<form id="new-search-form".*?</form>', html,
                     re.DOTALL).group()
    return re.findall(
      r'<input type="radio" name="search_object" value="(\w+)"( checked)?',
      form)


def trigger(html):
    """Return what makes the form send itself."""
    return re.search(r'<form id="new-search-form"[^>]*hx-trigger="([^"]+)"',
                     html).group(1)


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


def test_x_of_a_menu_keeps_it_closed(client, select_key):
    """Opened, it would cover the next field and take what is written there."""
    assert "'select2:opening', stayClosed" in selector_page(client, select_key)


def test_heading_is_a_heading_when_the_session_cache_is_lost(client,
                                                             select_key):
    """The session comes back from the database, and from JSON a plain text."""
    caches[settings.SESSION_CACHE_ALIAS].clear()
    html = selector_page(client, select_key)
    assert '<h2>Select story/issue' in html
    assert '&lt;h2&gt;' not in html


def bond_side_selector(client, bond, side):
    """Follow the button to edit a side of a bond, return the selector key."""
    indexer = bond.changeset.indexer
    indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(indexer)
    response = client.post(reverse('edit_series_bond', kwargs={'id': bond.id}),
                           {side: 'Change'})
    return resolve(response.url).kwargs['select_key']


def test_bond_heading_writes_a_name_as_text(db, client,
                                            any_added_series_bond_rev):
    """The names come from the indexers, and the heading is shown as html."""
    bond = any_added_series_bond_rev
    Series.objects.filter(id=bond.origin_id).update(
      name='<img src=x onerror=alert(1)>')
    key = bond_side_selector(client, bond, 'edit_origin')
    html = selector_page(client, key)
    assert '<img src=x' not in html
    assert '<h2>Select origin of the bond &lt;img src=x' in html


def test_headings_write_names_as_text(client, select_key, catalog,
                                      any_added_brand, any_edit_story_rev):
    """The view marks each heading safe, and each one holds indexers' names."""
    hostile = '<img src=x onerror=alert(1)>'
    Series.objects.filter(id=catalog['xmen91'].id).update(name=hostile)
    Brand.objects.filter(id=any_added_brand.id).update(name=hostile)
    indexer = any_edit_story_rev.changeset.indexer.indexer
    indexer.max_reservations = 5
    indexer.save()
    award = Award.objects.create(name=hostile)
    for key in (
      two_issues_selector(client, catalog),
      resolve(client.get(reverse(
        'add_brand_use', kwargs={'brand_id': any_added_brand.id})).url
              ).kwargs['select_key'],
      resolve(client.get(reverse(
        'select_award_recipient', kwargs={'award_id': award.id})).url
              ).kwargs['select_key']):
        html = selector_page(client, key)
        assert '<h2>' in html
        assert '<img src=x' not in html
        assert '&lt;img src=x' in html


def bond_selector(client, catalog):
    """Follow the link to add a series bond and return the selector key."""
    response = client.get(reverse('add_series_bond',
                                  kwargs={'series_id': catalog['xmen91'].id}))
    return resolve(response.url).kwargs['select_key']


def two_issues_selector(client, catalog):
    """Follow the link to edit two issues and return the selector key."""
    response = client.get(reverse('edit_two_issues',
                                  kwargs={'issue_id': catalog['a'].id}))
    return resolve(response.url).kwargs['select_key']


def test_one_set_of_fields_where_the_form_is(client, select_key, catalog):
    """The row asks for the same fields, and the form does what it does."""
    for key in (select_key, bond_selector(client, catalog),
                two_issues_selector(client, catalog)):
        html = selector_page(client, key)
        assert 'id="new-search-form"' in html
        assert 'class="select_search"' not in html
        assert 'by entering the relevant information' not in html
        for name in ('publisher', 'series', 'year', 'number', 'search_story',
                     'search_series'):
            assert f'name="{name}"' not in html
        assert html.count('name="issue_number"') == 1


def test_free_search_stays_where_the_form_is(client, select_key, catalog):
    """It is the one search by title."""
    for key in (select_key, bond_selector(client, catalog)):
        assert 'name="q"' in selector_page(client, key)


def test_sequence_number_is_where_stories_can_be_chosen(client, select_key,
                                                        catalog):
    assert 'name="sequence_number"' in selector_page(client, select_key)
    for key in (bond_selector(client, catalog),
                two_issues_selector(client, catalog)):
        assert 'name="sequence_number"' not in selector_page(client, key)


def test_form_is_where_issues_can_be_chosen(client, select_key, catalog):
    """It lists issues, and stories where the selector takes them."""
    for key in (select_key, bond_selector(client, catalog),
                two_issues_selector(client, catalog)):
        assert 'id="new-search-form"' in selector_page(client, key)


def test_brand_use_selector_has_no_form(client, select_key, any_added_brand):
    """A publisher cannot be chosen from its rows."""
    response = client.get(reverse('add_brand_use',
                                  kwargs={'brand_id': any_added_brand.id}))
    html = selector_page(client, resolve(response.url).kwargs['select_key'])
    assert 'id="new-search-form"' not in html
    assert 'id="new-search-results"' not in html
    assert 'name="search_publisher"' in html
    assert 'class="select_search"' in html
    assert 'by entering the relevant information' in html


def test_form_offers_all_first_and_checked(client, select_key):
    """The default lists both, as the free search on the page does."""
    html = selector_page(client, select_key)
    assert radio_buttons(html) \
        == [('all', ' checked'), ('story', ''), ('cover', ''), ('issue', '')]
    assert '<span>List:</span>' in html


def test_issue_selectors_have_no_radio_buttons(client, select_key, catalog):
    """They take issues alone: there is nothing to choose among."""
    for key in (bond_selector(client, catalog),
                two_issues_selector(client, catalog)):
        assert radio_buttons(selector_page(client, key)) == []


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
    assert radio_buttons(html)[0] == ('all', ' checked')


@pytest.mark.parametrize('choice', ['story', 'cover', 'target', 'return',
                                    'cancel', 'heading'])
def test_selector_refuses_what_it_does_not_take(client, select_key, catalog,
                                                choice):
    """
    A series bond would save the issue with the id of the story, and with the
    id of anything else the data of the selector has a value for.
    """
    bonds = SeriesBondRevision.objects.count()
    response = client.post(
      reverse('select_object',
              kwargs={'select_key': bond_selector(client, catalog)}),
      {'search_select': '1',
       'object_choice': f'{choice}_{catalog["a_story"].id}'})
    assert response.status_code == 400
    assert SeriesBondRevision.objects.count() == bonds


def test_select_this_cover_goes_on_as_its_story(client, select_key, catalog):
    """Its number is the id of a story: as an issue it is another comic."""
    cover = catalog['a_cover']
    with patch('apps.oi.views.confirm_reprint',
               return_value=HttpResponse('confirmation')) as confirm:
        response = client.post(
          reverse('select_object', kwargs={'select_key': select_key}),
          {'search_select': '1', 'object_choice': f'cover_{cover.id}'})
    assert response.content == b'confirmation'
    assert confirm.call_args.args[2:] == ('story', str(cover.id))


def test_form_needs_the_right_to_edit(client, catalog, any_edit_story_rev):
    """A lost session is an error the page writes, not a login page in it."""
    response = client.get(reverse('select_object_search_htmx',
                                  kwargs={'select_key': 'any'}),
                          {'issue_number': '1'})
    assert response.status_code == 403


def test_lost_selector_is_a_failing_status(client, select_key):
    """The page writes a failing status: an error page would land inside it."""
    response = client.get(reverse('select_object_search_htmx',
                                  kwargs={'select_key': 'lost'}),
                          {'issue_number': '1'})
    assert response.status_code == 400
    assert b'<html' not in response.content


def filled_values(html):
    """Return the values the form starts with, by field."""
    form = re.search(r'<form id="new-search-form".*?</form>', html,
                     re.DOTALL).group()
    found = {}
    for field in ('publisher_auto', 'series_auto'):
        select = re.search(r'<select[^>]*name="%s".*?</select>' % field, form,
                           re.DOTALL).group()
        found[field] = re.findall(r'<option value="(\d+)" selected', select)
    for field in ('series_year_auto', 'issue_number'):
        tag = re.search(r'<input[^>]*name="%s"[^>]*>' % field, form).group()
        value = re.search(r'value="([^"]*)"', tag)
        found[field] = value.group(1) if value else ''
    return found


@pytest.mark.parametrize('side, series, issue', [
  ('edit_origin', 'origin', 'origin_issue'),
  ('edit_target', 'target', 'target_issue')])
def test_editing_a_bond_fills_series_and_number(
        db, client, any_added_series_bond_rev, side, series, issue):
    """Publisher and year would narrow the menu of those who want another."""
    bond = any_added_series_bond_rev
    the_series = getattr(bond, series)
    setattr(bond, issue, Issue.objects.create(series=the_series, number='7',
                                              sort_code=1))
    bond.save()
    html = selector_page(client, bond_side_selector(client, bond, side))
    assert filled_values(html) == {'publisher_auto': [],
                                   'series_auto': [str(the_series.id)],
                                   'series_year_auto': '',
                                   'issue_number': '7'}
    assert trigger(html) == SEARCH_ON_OPEN


def test_series_only_bond_fills_no_number(db, client,
                                          any_added_series_bond_rev):
    bond = any_added_series_bond_rev
    html = selector_page(client, bond_side_selector(client, bond,
                                                    'edit_origin'))
    assert filled_values(html)['series_auto'] == [str(bond.origin_id)]
    assert filled_values(html)['issue_number'] == ''


def test_only_a_filled_form_lists_at_load(client, select_key, catalog):
    """An empty form has nothing to ask, on every page of a selector."""
    for key in (select_key, bond_selector(client, catalog)):
        html = selector_page(client, key)
        assert filled_values(html)['series_auto'] == []
        assert trigger(html) == 'change delay:500ms'


@pytest.mark.parametrize('side', ['edit_origin', 'edit_target'])
def test_change_of_a_side_fills_the_form(client, select_key, catalog,
                                         any_edit_story_rev, side):
    """It lists every sequence of the issue: this one is being changed."""
    story = any_edit_story_rev.story
    sides = {'origin': catalog['second_story'], 'target': story} \
        if side == 'edit_origin' \
        else {'origin': story, 'target': catalog['second_story']}
    link = ReprintRevision.objects.create(
      changeset=any_edit_story_rev.changeset,
      origin=sides['origin'], origin_issue=sides['origin'].issue,
      target=sides['target'], target_issue=sides['target'].issue)
    response = client.post(reverse('edit_reprint', kwargs={'id': link.id}),
                           {side: 'Change'})
    html = selector_page(client, resolve(response.url).kwargs['select_key'])
    assert filled_values(html) == {'publisher_auto': [],
                                   'series_auto': [str(catalog['xmen91'].id)],
                                   'series_year_auto': '',
                                   'issue_number': '2'}
    assert trigger(html) == SEARCH_ON_OPEN
    number = re.search(r'<input[^>]*name="sequence_number"[^>]*>', html)
    assert 'value=' not in number.group()


def note_selector(client, revision, note):
    """Follow Add Reprint from a reprint note and return the selector key."""
    response = client.get(reverse(
      'add_story_reprint',
      kwargs={'story_id': revision.id,
              'changeset_id': revision.changeset_id,
              'reprint_note': note}))
    return resolve(response.url).kwargs['select_key']


def test_note_of_one_series_fills_the_form(client, select_key, catalog,
                                           any_edit_story_rev):
    note = 'from X-Men (Marvel, 1991 series) #2'
    html = selector_page(client,
                         note_selector(client, any_edit_story_rev, note))
    assert filled_values(html)['series_auto'] == [str(catalog['xmen91'].id)]
    assert filled_values(html)['issue_number'] == '2'
    assert trigger(html) == SEARCH_ON_OPEN
    assert f'<p>Reprint note: {note}</p>' in html


@pytest.mark.parametrize('note', ['from Nothing (Nobody, 1900 series) #1',
                                  'from Nothing (Nobody, 1900 series) #1 -',
                                  'Donald Duck daily 1944-03-28'])
def test_other_note_is_only_shown(client, select_key, catalog,
                                  any_edit_story_rev, note):
    """It names no series of the catalog, or it has not the standard form."""
    html = selector_page(client,
                         note_selector(client, any_edit_story_rev, note))
    assert filled_values(html)['series_auto'] == []
    assert trigger(html) == 'change delay:500ms'
    assert f'<p>Reprint note: {note}</p>' in html


def test_button_of_a_sequence_without_notes_shows_no_note(
        client, select_key, catalog, any_edit_story_rev):
    """It sends a space, and the page must not say an empty Reprint note."""
    html = selector_page(client,
                         note_selector(client, any_edit_story_rev, ' '))
    assert 'Reprint note' not in html
    assert trigger(html) == 'change delay:500ms'


def test_note_is_shown_whole_and_fills_from_its_first_part(
        client, select_key, catalog, any_edit_story_rev):
    note = 'from X-Men (Marvel, 1991 series) #2; in Other (A, 2000 series) #1'
    html = selector_page(client,
                         note_selector(client, any_edit_story_rev, note))
    assert f'<p>Reprint note: {note}</p>' in html
    assert filled_values(html)['series_auto'] == [str(catalog['xmen91'].id)]


def test_note_of_twin_series_fills_nothing(client, select_key, catalog,
                                           any_edit_story_rev):
    """It cannot say which one it means."""
    another_series(catalog, 'X-Men', year_began=1991)
    html = selector_page(client, note_selector(
      client, any_edit_story_rev, 'from X-Men (Marvel, 1991 series) #2'))
    assert filled_values(html)['series_auto'] == []


def test_note_is_written_as_text(client, select_key, catalog,
                                 any_edit_story_rev):
    """The heading is marked safe in the view, and a note is free text."""
    html = selector_page(client, note_selector(
      client, any_edit_story_rev, 'from <img src=x onerror=alert(1)>'))
    assert '<img src=x' not in html
    assert '&lt;img src=x' in html


def test_bond_selects_the_chosen_series_too(client, select_key, catalog):
    """An end of a bond can be a whole series."""
    key = bond_selector(client, catalog)
    url = reverse('select_object_search_htmx', kwargs={'select_key': key})
    series = catalog['xmen91'].id
    response = client.get(url, {'series_auto': series, 'issue_number': '2'})
    html = response.content.decode()
    assert results(response) == {f'series_{series}',
                                 f'issue_{catalog["second"].id}'}
    assert html.index('Select This Series') < html.index('Select This Issue')
    assert '1 to 1 of 1 objects' in ' '.join(html.split())
    assert ' '.join(html.split()).count('of 1 objects') == 1
    too_many_of_each(catalog)
    response = client.get(url, {'series_auto': series})
    assert 'Select This Series' in response.content.decode()
    assert response.content.endswith(ASK_NUMBER)


def test_chosen_series_is_not_repeated_on_the_pages_of_a_table(
        client, select_key, catalog):
    key = bond_selector(client, catalog)
    response = client.get(
      reverse('select_object_search_htmx', kwargs={'select_key': key}),
      {'series_auto': catalog['xmen91'].id, 'issue_number': '2', 'page': '1'})
    assert 'Select This Series' not in response.content.decode()


def test_series_is_not_offered_where_the_selector_takes_none(client,
                                                             select_key,
                                                             catalog):
    for key in (select_key, two_issues_selector(client, catalog)):
        response = client.get(
          reverse('select_object_search_htmx', kwargs={'select_key': key}),
          {'series_auto': catalog['xmen91'].id, 'issue_number': '2'})
        assert 'Select This Series' not in response.content.decode()


def test_select_this_series_saves_the_bond_on_the_series(client, select_key,
                                                         catalog):
    response = client.post(
      reverse('select_object',
              kwargs={'select_key': bond_selector(client, catalog)}),
      {'search_select': '1', 'object_choice': f'series_{catalog["x"].id}'})
    assert response.status_code == 302
    bond = SeriesBondRevision.objects.latest('id')
    assert bond.target == catalog['x']
    assert bond.target_issue is None


def test_award_selects_the_chosen_series_too(client, select_key, catalog,
                                             any_edit_story_rev):
    indexer = any_edit_story_rev.changeset.indexer.indexer
    indexer.max_reservations = 5
    indexer.save()
    award = Award.objects.create(name='Any award')
    key = resolve(client.get(reverse(
      'select_award_recipient', kwargs={'award_id': award.id})).url
                  ).kwargs['select_key']
    series = catalog['xmen91'].id
    response = client.get(
      reverse('select_object_search_htmx', kwargs={'select_key': key}),
      {'series_auto': series, 'issue_number': '2'})
    assert f'series_{series}' in results(response)
    response = client.post(
      reverse('select_object', kwargs={'select_key': key}),
      {'search_select': '1', 'object_choice': f'series_{series}'})
    assert response.url == reverse(
      'add_received_award',
      kwargs={'award_id': award.id, 'model_name': 'series', 'id': series})


def test_filled_series_shows_its_name_as_text(db, client,
                                              any_added_series_bond_rev):
    """The names come from the indexers."""
    bond = any_added_series_bond_rev
    Series.objects.filter(id=bond.origin_id).update(name='<b>Origin</b>')
    html = selector_page(client, bond_side_selector(client, bond,
                                                    'edit_origin'))
    assert f'<option value="{bond.origin_id}" selected>&lt;b&gt;Origin' in html


def test_filled_series_reads_as_in_its_menu(client, select_key, catalog,
                                            any_edit_story_rev):
    html = selector_page(client, note_selector(
      client, any_edit_story_rev, 'from X-Men (Marvel, 1991 series) #2'))
    label = menu(client, select_key, 'series_auto', str(catalog['xmen91'].id)
                 )[0]['text']
    assert label.startswith('X-Men (Marvel, 1991 series) - XA, 118 issues')
    assert f'selected>{label}</option>' in html


def test_empty_form_lists_nothing(client, select_key):
    response = search(client, select_key, publisher_auto='', series_auto='',
                      series_year_auto='', issue_number='')
    assert response.status_code == 200
    assert response.content == b''


@pytest.mark.parametrize('form', [{'sequence_number': '7'},
                                  {'series_year_auto': '-1'},
                                  {'series_year_auto': '19.4'}])
def test_field_that_narrows_nothing_alone_asks_for_a_series(client, select_key,
                                                            form):
    """No field is required, and none is answered with silence."""
    assert search(client, select_key, **form).content == ASK_SERIES


def test_free_search_lists_only_what_the_selector_takes(client, select_key):
    """The row of anything else would have no button."""
    with patch('apps.gcd.views.search_haystack.PaginatedFacetedSearchView'
               ) as view:
        view.return_value.return_value = HttpResponse('')
        client.get(reverse('select_object_search_haystack',
                           kwargs={'select_key': select_key}), {'q': 'batman'})
    assert view.call_args.kwargs['template'] == 'search/tw_search.html'
    searched = str(view.call_args.kwargs['searchqueryset'].query.query_filter)
    assert "('facet_model_name__in', ['issue', 'story'])" in searched


def options_of_the_results(**context):
    """Return the choices of the menu of the page of the free search."""
    return re.findall(r'value="([^"]+)"',
                      render_to_string('gcd/bits/hs_search_for.html', context))


def test_results_of_a_selector_offer_only_what_it_takes():
    assert options_of_the_results(allowed_selects=['issue', 'story']) == [
      'all', 'issue', 'story']
    selected = render_to_string(
      'gcd/bits/hs_search_for.html',
      {'allowed_selects': ['issue', 'story'],
       'selected_model': 'facet_model_name_exact:story'})
    assert '<option value="story" selected>' in selected


@pytest.mark.parametrize('context', [
  {}, {'allowed_selects': ['issue', 'story'], 'multiple_selects': True}])
def test_other_results_offer_every_kind_as_before(context):
    """The search of the site, and the one of the collections."""
    assert options_of_the_results(**context) == [
      'all', 'story', 'issue', 'series', 'publisher', 'printer', 'creator']


def test_free_search_is_not_sent_empty(client, select_key):
    """It would reload the page and empty the form below it."""
    bar = re.search(r'<input[^>]*name="q"[^>]*>',
                    selector_page(client, select_key)).group()
    assert 'required' in bar


# Back and reload


def selector_address(select_key, query):
    """Return the address of the page of a selector with the given query."""
    return reverse('select_object', kwargs={'select_key': select_key}) \
        + '?' + query


def test_search_writes_itself_in_the_address(client, select_key, catalog):
    series = catalog['xmen91'].id
    response = search(client, select_key, series_auto=series,
                      issue_number='1 [Cover A]', search_object='cover')
    assert response['HX-Replace-Url'] == selector_address(
      select_key,
      f'series_auto={series}&issue_number=1+%5BCover+A%5D&search_object=cover')


def test_emptied_form_writes_itself_in_the_address(client, select_key):
    """Back must not bring back what was just cleared."""
    response = search(client, select_key, issue_number='')
    assert response['HX-Replace-Url'] == selector_address(select_key,
                                                          'issue_number=')


def test_page_of_a_table_leaves_the_address(client, select_key, catalog):
    """The page would come back as the first page of what the form finds."""
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      page='1')
    assert 'HX-Replace-Url' not in response


def test_address_fills_the_form_and_lists(client, select_key, catalog):
    series = catalog['xmen91'].id
    html = client.get(selector_address(
      select_key,
      f'series_auto={series}&series_year_auto=&issue_number=2'
      '&sequence_number=1&search_object=cover')).content.decode()
    assert filled_values(html) == {'publisher_auto': [],
                                   'series_auto': [str(series)],
                                   'series_year_auto': '',
                                   'issue_number': '2'}
    number = re.search(r'<input[^>]*name="sequence_number"[^>]*>', html)
    assert 'value="1"' in number.group()
    assert ('cover', ' checked') in radio_buttons(html)
    assert ('all', ' checked') not in radio_buttons(html)
    assert trigger(html) == SEARCH_ON_OPEN


def test_address_wins_over_what_the_note_filled(client, select_key, catalog,
                                                any_edit_story_rev):
    """What was changed or cleared stays so."""
    key = note_selector(client, any_edit_story_rev,
                        'from X-Men (Marvel, 1991 series) #2')
    html = client.get(selector_address(key, 'issue_number=3&search_object=all')
                      ).content.decode()
    assert filled_values(html)['series_auto'] == []
    assert filled_values(html)['issue_number'] == '3'


def test_empty_free_search_leaves_what_the_note_filled(client, select_key,
                                                       catalog,
                                                       any_edit_story_rev):
    """Its address has no number: it is not a search of the form."""
    key = note_selector(client, any_edit_story_rev,
                        'from X-Men (Marvel, 1991 series) #2')
    html = client.get(selector_address(key, 'q=&search_object=all')
                      ).content.decode()
    assert filled_values(html)['series_auto'] == [str(catalog['xmen91'].id)]


def test_address_is_written_as_text(client, select_key):
    html = client.get(selector_address(
      select_key, 'issue_number=%22%3E%3Cimg+src%3Dx%3E')).content.decode()
    assert '<img src=x>' not in html
    assert '&quot;&gt;&lt;img src=x&gt;' in html


@pytest.mark.parametrize('value', ['abc', '1.5', '-1'])
def test_address_with_a_menu_value_that_is_no_id_lists_no_rows(
        client, select_key, catalog, value):
    """The menu would write all its rows in the page: 233,636 on the site."""
    html = client.get(selector_address(
      select_key, f'publisher_auto={value}&series_auto={value}&issue_number=1')
      ).content.decode()
    assert filled_values(html) == {'publisher_auto': [], 'series_auto': [],
                                   'series_year_auto': '', 'issue_number': '1'}
    assert f'<option value="{catalog["xmen91"].id}"' not in html
    assert f'<option value="{catalog["marvel"].id}"' not in html


def test_address_with_an_id_too_long_for_the_database_lists_no_rows(
        client, select_key, catalog):
    html = client.get(selector_address(
      select_key, f'series_auto={"9" * 30}&issue_number=1')).content.decode()
    assert filled_values(html)['series_auto'] == []


@pytest.mark.parametrize('field', ['publisher_auto', 'series_auto'])
def test_search_leaves_out_a_menu_value_that_is_no_id(client, select_key,
                                                      catalog, field):
    assert search(client, select_key, **{field: 'abc'}).content == b''
    response = search(client, select_key, issue_number='1', **{field: 'abc'})
    assert response.status_code == 200
    assert results(response) == story_rows(catalog, 'uk_cover', 'uk_story')


def test_search_bears_an_id_too_long_for_the_database(client, select_key):
    response = search(client, select_key, series_auto='9' * 30)
    assert response.status_code == 200
    assert b'No results.' in response.content


def test_address_with_an_unknown_choice_checks_all(client, select_key):
    html = client.get(selector_address(
      select_key, 'issue_number=1&search_object=series')).content.decode()
    assert ('all', ' checked') in radio_buttons(html)


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
    assert menu(client, select_key, 'series_auto', issue_number='999',
                publisher=str(catalog['marvel'].id)) == NO_SERIES


def test_text_no_series_has_is_not_blamed_on_the_number(client, select_key,
                                                        catalog):
    assert menu(client, select_key, 'series_auto', 'zzzzz', issue_number='1',
                publisher=str(catalog['marvel'].id)) == NO_SERIES_NAMED


def test_deleted_issue_does_not_narrow_the_series_menu(client, select_key,
                                                       catalog):
    Issue.objects.create(series=catalog['xmen91'], number='7', sort_code=8,
                         deleted=True)
    assert menu(client, select_key, 'series_auto', 'xmen', issue_number='7',
                publisher=str(catalog['marvel'].id)) == NO_SERIES_NAMED


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
    html = response.content.decode()
    assert '<p>No results.</p>' in html
    assert '<table' not in html
    assert '0 of 0' not in html


# the radio buttons


def test_story_choice_lists_only_stories(client, select_key, catalog):
    """Not the issues without sequences that all lists below them."""
    Issue.objects.create(series=catalog['xmen91'], sort_code=9, number='2 [B]')
    response = search(client, select_key, search_object='story',
                      series_auto=catalog['xmen91'].id, issue_number='2')
    assert results(response) == story_rows(catalog, 'second_cover',
                                           'second_story')


def test_cover_choice_lists_only_covers(client, select_key, catalog):
    response = search(client, select_key, search_object='cover',
                      series_auto=catalog['xmen91'].id, issue_number='2')
    html = response.content.decode()
    assert results(response) == cover_rows(catalog, 'second')
    assert html.count('Select This Cover') == 1
    assert html.count('Select This Issue') == 1
    assert 'Select This Story' not in html


def test_issue_choice_lists_issues_with_sequences(client, select_key, catalog):
    """All lists only those without: this choice has one row for each."""
    empty = Issue.objects.create(series=catalog['xmen91'], sort_code=9,
                                 number='2 [B]')
    response = search(client, select_key, search_object='issue',
                      series_auto=catalog['xmen91'].id, issue_number='2')
    html = response.content.decode()
    assert results(response) == {f'issue_{catalog["second"].id}',
                                 f'issue_{empty.id}'}
    assert html.count('Select This Issue') == 2
    assert 'Select This Story' not in html


def test_sequence_number_narrows_the_stories(client, select_key, catalog):
    """The rows do not show it, and the issues without sequences have none."""
    Issue.objects.create(series=catalog['xmen91'], sort_code=9, number='2 [B]')
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2', sequence_number='1')
    assert results(response) == story_rows(catalog, 'second_story')


def test_sequence_number_zero_is_a_number(client, select_key, catalog):
    """Covers are mostly sequence 0."""
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2', sequence_number='0')
    assert results(response) == story_rows(catalog, 'second_cover')


def test_sequence_number_that_is_no_number_is_left_out(client, select_key,
                                                       catalog):
    response = search(client, select_key, series_auto=catalog['xmen91'].id,
                      issue_number='2', sequence_number='abc')
    assert results(response) == story_rows(catalog, 'second_cover',
                                           'second_story')


def test_unknown_choice_counts_as_all(client, select_key, catalog):
    form = {'series_auto': catalog['xmen91'].id, 'issue_number': '2'}
    assert results(search(client, select_key, search_object='any', **form)) \
        == results(search(client, select_key, **form)) \
        == story_rows(catalog, 'second_cover', 'second_story')


@pytest.mark.parametrize('form, headers', [
  ({'search_object': 'story'}, {}),
  ({'search_object': 'cover'}, {}),
  ({}, {'HX-Target': 'story-results'})])
def test_issue_selector_ignores_what_the_request_asks(client, select_key,
                                                      catalog, form, headers):
    """A row of a story would save its id as an issue of the bond."""
    response = client.get(
      reverse('select_object_search_htmx',
              kwargs={'select_key': bond_selector(client, catalog)}),
      {'series_auto': catalog['xmen91'].id, 'issue_number': '2', **form},
      headers=headers)
    assert results(response) == {f'issue_{catalog["second"].id}',
                                 f'series_{catalog["xmen91"].id}'}
    assert 'Select This Story' not in response.content.decode()


@pytest.mark.parametrize('extra, too_many', [(FEW_RESULTS - 4, False),
                                             (FEW_RESULTS - 3, True)])
def test_issue_choice_counts_all_issues(client, select_key, catalog, extra,
                                        too_many):
    """The 4 issues of the series with sequences count, not only the others."""
    for number in range(extra):
        Issue.objects.create(series=catalog['xmen91'], number=f'{number + 20}',
                             sort_code=number + 20)
    response = search(client, select_key, search_object='issue',
                      series_auto=catalog['xmen91'].id)
    if too_many:
        assert response.content == ASK_NUMBER
    else:
        assert len(results(response)) == FEW_RESULTS


@pytest.mark.parametrize('kind, reads', [('all', True), ('story', False),
                                         ('cover', False), ('issue', False)])
def test_only_all_reads_issues_without_sequences(client, select_key, catalog,
                                                 kind, reads):
    """Among all the issues of a publisher that query takes seconds."""
    url = search_url(client, select_key)
    with CaptureQueriesContext(connection) as queries:
        client.get(url, {'search_object': kind,
                         'publisher_auto': catalog['marvel'].id})
    assert any('NOT EXISTS' in query['sql'] for query in queries) == reads


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
        assert response.content == ASK_NUMBER
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


def many_stories(catalog, number, how_many, kind='comic story'):
    """Add stories to the issue of the given short name."""
    story_type = StoryType.objects.get(name=kind)
    for sequence_number in range(how_many):
        Story.objects.create(issue=catalog[number], type=story_type,
                             sequence_number=sequence_number + 2)


def too_many_of_each(catalog):
    """Add to X-Men of 1991 more than the limit of covers and of issues."""
    many_stories(catalog, 'second', FEW_RESULTS, kind='cover')
    for number in range(FEW_RESULTS):
        Issue.objects.create(series=catalog['xmen91'], number=f'{number + 20}',
                             sort_code=number + 20)


@pytest.mark.parametrize('kind', ['all', 'story', 'cover', 'issue'])
def test_too_many_of_a_series_ask_for_the_number(client, select_key, catalog,
                                                 kind):
    too_many_of_each(catalog)
    response = search(client, select_key, search_object=kind,
                      series_auto=catalog['xmen91'].id)
    assert response.content == ASK_NUMBER


@pytest.mark.parametrize('kind', ['all', 'story', 'cover', 'issue'])
def test_too_many_results_ask_for_the_series(client, select_key, catalog,
                                             kind):
    too_many_of_each(catalog)
    response = search(client, select_key, search_object=kind,
                      publisher_auto=catalog['marvel'].id)
    assert response.content == ASK_SERIES


def test_issue_selector_too_many_offers_no_covers(client, select_key, catalog):
    """It has no radio buttons to go to, whatever the request asks."""
    too_many_of_each(catalog)
    key = two_issues_selector(client, catalog)
    response = client.get(reverse('select_object_search_htmx',
                                  kwargs={'select_key': key}),
                          {'search_object': 'story',
                           'series_auto': catalog['xmen91'].id})
    assert response.content == ASK_NUMBER


@pytest.mark.parametrize('kind', ['cover', 'issue'])
def test_other_choices_list_what_stories_would_hide(client, select_key,
                                                    catalog, kind):
    """The radio buttons limit the results: this is what they are for."""
    many_stories(catalog, 'second', FEW_RESULTS)
    series = catalog['xmen91'].id
    assert search(client, select_key, series_auto=series).content == ASK_NUMBER
    assert results(search(client, select_key, series_auto=series,
                          search_object=kind))


def test_series_of_one_issue_always_lists(client, select_key, catalog):
    """A number would narrow nothing, and it may well be [nn]."""
    many_stories(catalog, 'uk', FEW_RESULTS + 5)
    response = search(client, select_key, series_auto=catalog['xmen_uk'].id)
    assert stories_listed(response) == FEW_RESULTS + 7


def test_deleted_issue_does_not_count_for_a_series_of_one_issue(
        client, select_key, catalog):
    many_stories(catalog, 'uk', FEW_RESULTS + 5)
    Issue.objects.create(series=catalog['xmen_uk'], number='2', sort_code=2,
                         deleted=True)
    response = search(client, select_key, series_auto=catalog['xmen_uk'].id)
    assert stories_listed(response) == FEW_RESULTS + 7


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


def long_table(client, select_key, catalog, **form):
    """Return the first page of the 102 stories of an issue."""
    many_stories(catalog, 'second', 100)
    return search(client, select_key, series_auto=catalog['xmen91'].id,
                  issue_number='2', publisher_auto='', series_year_auto='',
                  **form)


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


def test_links_and_box_keep_the_choice(client, select_key, catalog):
    response = long_table(client, select_key, catalog, search_object='story')
    assert 'search_object=story' in page_links(response)[2]
    html = response.content.decode()
    box = re.search(r'<form method="GET" action="[^"]+">.*?</form>', html,
                    re.DOTALL)
    assert 'name="search_object" value="story"' in box.group()


def test_cover_table_pages_by_itself(client, select_key, catalog):
    """Its links answer in its own place, with the rest of the covers."""
    many_stories(catalog, 'second', 100, kind='cover')
    response = search(client, select_key, search_object='cover',
                      series_auto=catalog['xmen91'].id, issue_number='2')
    html = response.content.decode()
    assert 'id="cover-results"' in html
    assert 'hx-target="#cover-results"' in html
    second = client.get(page_links(response)[2])
    assert 'id="cover-results"' in second.content.decode()
    assert len([choice for choice in results(second)
                if choice.startswith('cover_')]) == 1


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
