# -*- coding: utf-8 -*-
"""The sequence form hides the fields that do not apply to the type."""

import html
import json
import re

import pytest

from django.urls import reverse

from crispy_forms.layout import HTML

from apps.gcd.models import StoryType
from apps.oi.forms.story import StoryRevisionForm, _hidden_rows
from apps.oi.models import CTYPES, StoryRevision

FEATURE_AND_GENRE = {'feature', 'feature_name', 'feature_genres',
                     'feature_logo', 'genre', 'selected_genres'}
FORMSETS = ['story_credit_revisions', 'story_character_revisions',
            'story_group_revisions']


def _hidden_names(type_name):
    """The names of the form rows the type hides."""
    type_id = StoryType.objects.get(name=type_name).id
    return {name for rows, shown_by in _hidden_rows().get(type_id, [])
            for name in rows}


@pytest.mark.django_db
def test_rows_hidden_by_type():
    """Rows of the Not applicable and Forbidden fields of a type."""
    assert _hidden_names('comic story') == set()
    assert _hidden_names('cover') == {'feature_logo'}
    for type_name in ['credits, title page', 'table of contents',
                      'statement of ownership']:
        assert _hidden_names(type_name) == FEATURE_AND_GENRE
    blank = _hidden_names('blank page(s)')
    assert FEATURE_AND_GENRE | {
      'title', 'first_line', 'story_arc', 'job_number', 'script', 'editing',
      'story_credit_revisions', 'universe', 'characters', 'character_order',
      'story_character_revisions', 'story_group_revisions', 'synopsis',
      'reprint_notes', 'keywords'} <= blank
    assert not {'type', 'page_count', 'page_count_uncertain', 'no_script',
                'no_editing', 'notes', 'comments'} & blank


def _html_rows(layout):
    """The HTML snippets of a crispy layout, also inside tabs."""
    for field in layout.fields:
        if isinstance(field, HTML):
            yield field.html
        elif hasattr(field, 'fields'):
            yield from _html_rows(field)


@pytest.mark.django_db
@pytest.mark.parametrize('use_tabs', [False, True])
def test_hidden_rows_exist_in_the_form(any_indexer, use_tabs):
    """Each hidden row is a field, a formset or a marked row of the form."""
    any_indexer.indexer.use_tabs = use_tabs
    form = StoryRevisionForm(user=any_indexer, instance=StoryRevision())
    snippets = list(_html_rows(form.helper.layout))
    rows_html = ''.join(snippets)
    for groups in _hidden_rows().values():
        for rows, shown_by in groups:
            assert set(shown_by) <= set(rows)
            for name in rows:
                # the characters heading is not in the tab layout
                assert name in form.fields or name in FORMSETS or \
                    'name="%s"' % name in rows_html or \
                    'data-field="%s"' % name in rows_html or \
                    (use_tabs and name == 'characters_heading'), name
    # a data-field marks a whole row
    assert set(re.findall(r'<(\w+)[^>]*data-field=', rows_html)) == {'tr'}
    order_row, = [snippet for snippet in snippets
                  if 'data-field="character_order"' in snippet]
    assert order_row.endswith('</td></tr>')


@pytest.mark.django_db
def test_edit_page_tells_the_rows_to_hide(client, any_indexer,
                                          any_edit_story_rev):
    """The Type field of the page carries the rows each type hides."""
    # the edit page of a sequence is that of a change to its issue
    changeset = any_edit_story_rev.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    response = client.get(reverse('edit_revision', kwargs={
      'model_name': 'story', 'id': any_edit_story_rev.id}))

    assert response.status_code == 200
    select = re.search(r'<select name="type"[^>]*>',
                       response.content.decode()).group(0)
    hidden_rows = re.search(r'data-hidden-rows="([^"]*)"', select).group(1)
    assert json.loads(html.unescape(hidden_rows)) == \
        json.loads(json.dumps(_hidden_rows()))


@pytest.mark.django_db
def test_checked_unofficial_box_stays_shown_on_blank_pages(any_indexer):
    """
    On a blank page an empty title with the Unofficial title box checked
    cannot be saved, so the box stays shown and can be unchecked.
    """
    blank = StoryType.objects.get(name='blank page(s)').id
    data = {'sequence_number': '0', 'type': str(blank), 'title': '',
            'title_inferred': 'on'}
    form = StoryRevisionForm(data, user=any_indexer,
                             instance=StoryRevision())
    assert not form.is_valid()
    assert form.non_field_errors() == ['Empty titles cannot be unofficial.']
    # the rule of storyrevision_form_utils.js: the rows of a group are
    # hidden unless one of the fields that keep them shown holds a value
    hidden = {name for rows, shown_by in _hidden_rows()[blank]
              if not any(data.get(field) for field in shown_by)
              for name in rows}
    assert 'title_inferred' not in hidden
