# -*- coding: utf-8 -*-
"""Tests of the selector page of reprint links and series bonds."""

import re

import pytest

from django.contrib.auth.models import Permission
from django.urls import resolve, reverse

from apps.gcd.models import Issue, Publisher, Series, Story, StoryType
from apps.oi.models import ReprintRevision
from apps.stddata.models import Country, Language

pytestmark = pytest.mark.django_db


def log_in(client, changeset):
    """Log in the indexer of the changeset, with the right to edit."""
    indexer = changeset.indexer
    indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(indexer)


def selector_page(client, response):
    """Follow the redirect to the selector and return the html of its page."""
    select_key = resolve(response.url).kwargs['select_key']
    return client.get(reverse('select_object',
                              kwargs={'select_key': select_key})
                      ).content.decode()


def note_page(client, revision, note):
    """Follow Add Reprint from a reprint note and return the page."""
    log_in(client, revision.changeset)
    return selector_page(client, client.get(reverse(
      'add_story_reprint',
      kwargs={'story_id': revision.id, 'changeset_id': revision.changeset_id,
              'reprint_note': note})))


def test_reprint_note_is_shown_after_the_heading(client, any_edit_story_rev):
    """A paragraph inside the h2 is no valid html, and it reads as a title."""
    note = 'from Tom & Jerry (Dell, 1948 series) #1'
    html = note_page(client, any_edit_story_rev, note)
    heading = re.search(r'<h2>(.*?)</h2>', html, re.DOTALL).group(1)
    assert 'Reprint note' not in heading
    assert html.count('Reprint note:') == 1
    assert re.search(r'</h2>\s*<p>Reprint note: from Tom &amp; Jerry '
                     r'\(Dell, 1948 series\) #1</p>', html)


@pytest.fixture
def catalog():
    """Return X-Men of 1991 from Marvel and the first sequence of its #2."""
    country = Country.objects.get_or_create(
      code='xa', defaults={'name': 'Row country'})[0]
    language = Language.objects.get_or_create(
      code='xa', defaults={'name': 'Row language'})[0]
    marvel = Publisher.objects.create(name='Marvel', country=country,
                                      year_began=1939)
    xmen = Series.objects.create(
      name='X-Men', sort_name='X-Men', publisher=marvel, country=country,
      language=language, year_began=1991)
    issue = Issue.objects.create(series=xmen, number='2', sort_code=1)
    story = Story.objects.create(
      issue=issue, sequence_number=1,
      type=StoryType.objects.get(name='comic story'))
    return {'series': xmen, 'story': story}


def row_values(html):
    """Return the values the row of the older search starts with, by field."""
    row = re.search(r'<table class="select_search">.*?</table>', html,
                    re.DOTALL).group()
    found = {}
    for tag in re.findall(r'<input[^>]*>', row):
        name = re.search(r'name="([^"]+)"', tag).group(1)
        if name == 'select_key':
            continue
        value = re.search(r'value="([^"]*)"', tag)
        found[name] = value.group(1) if value else ''
    return found


def form_values(html):
    """Return the series and the number the form starts with."""
    form = re.search(r'<form id="new-search-form".*?</form>', html,
                     re.DOTALL).group()
    series = re.search(r'<select[^>]*name="series_auto".*?</select>', form,
                       re.DOTALL).group()
    number = re.search(r'<input[^>]*name="issue_number"[^>]*>', form).group()
    value = re.search(r'value="([^"]*)"', number)
    return (re.findall(r'<option value="(\d+)" selected', series),
            value.group(1) if value else '')


@pytest.mark.parametrize('side', ['edit_origin', 'edit_target'])
def test_change_of_a_side_fills_the_row(client, catalog, any_edit_story_rev,
                                        side):
    """The row starts with the sequence being changed, as before the form."""
    story = any_edit_story_rev.story
    sides = {'origin': catalog['story'], 'target': story} \
        if side == 'edit_origin' \
        else {'origin': story, 'target': catalog['story']}
    link = ReprintRevision.objects.create(
      changeset=any_edit_story_rev.changeset,
      origin=sides['origin'], origin_issue=sides['origin'].issue,
      target=sides['target'], target_issue=sides['target'].issue)
    log_in(client, link.changeset)
    html = selector_page(client, client.post(
      reverse('edit_reprint', kwargs={'id': link.id}), {side: 'Change'}))
    assert row_values(html) == {'publisher': 'Marvel', 'series': 'X-Men',
                                'year': '1991', 'number': '2',
                                'sequence_number': '1'}
    assert form_values(html) == ([str(catalog['series'].id)], '2')


@pytest.mark.parametrize('side, series, issue', [
  ('edit_origin', 'origin', 'origin_issue'),
  ('edit_target', 'target', 'target_issue')])
def test_editing_a_bond_fills_the_row(client, any_added_series_bond_rev,
                                      side, series, issue):
    bond = any_added_series_bond_rev
    the_series = getattr(bond, series)
    setattr(bond, issue, Issue.objects.create(series=the_series, number='7',
                                              sort_code=1))
    bond.save()
    log_in(client, bond.changeset)
    html = selector_page(client, client.post(
      reverse('edit_series_bond', kwargs={'id': bond.id}), {side: 'Change'}))
    assert row_values(html) == {'publisher': the_series.publisher.name,
                                'series': the_series.name,
                                'year': str(the_series.year_began),
                                'number': '7'}
    assert form_values(html) == ([str(the_series.id)], '7')


def test_note_of_a_known_series_fills_the_row(client, catalog,
                                              any_edit_story_rev):
    html = note_page(client, any_edit_story_rev,
                     'from X-Men (Marvel, 1991 series) #2')
    assert row_values(html) == {'publisher': 'Marvel', 'series': 'X-Men',
                                'year': '1991', 'number': '2',
                                'sequence_number': ''}
    assert form_values(html) == ([str(catalog['series'].id)], '2')


def test_note_of_an_unknown_series_fills_the_row(client, any_edit_story_rev):
    """The form cannot take a series not in the catalog, the row can."""
    html = note_page(client, any_edit_story_rev,
                     'from Nothing (Nobody, 1900 series) #1')
    assert row_values(html) == {'publisher': 'Nobody', 'series': 'Nothing',
                                'year': '1900', 'number': '1',
                                'sequence_number': ''}
    assert form_values(html) == ([], '')
