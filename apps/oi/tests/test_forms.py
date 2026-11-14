# -*- coding: utf-8 -*-


import re
import mock
import pytest

from dal import autocomplete
from django.forms import ValidationError

from apps.oi.forms.story import (
    StoryCharacterRevisionForm, StoryCreditRevisionForm,
    StoryGroupRevisionForm, StoryRevisionForm)
from apps.oi.forms.support import KeywordsWidget, KeywordsField


@pytest.fixture
def tag_objects():

    foo = mock.MagicMock()
    foo.name = 'Foo'
    foo.slug = 'foo'

    bar_baz = mock.MagicMock()
    bar_baz.name = 'Bar Baz'
    bar_baz.slug = 'bar-baz'

    more_words = mock.MagicMock()
    more_words.name = 'these. are. more words'
    more_words.slug = 'these-are-more-words'

    return [mock.MagicMock(tag=bar_baz),
            mock.MagicMock(tag=foo),
            mock.MagicMock(tag=more_words)]


@pytest.fixture
def tag_list(tag_objects):
    return [o.tag.name for o in tag_objects]


@pytest.fixture
def tag_string(tag_list):
    return '; '.join(tag_list)


def test_keywords_widget(tag_objects, tag_string):
    # Semantically weird, but works for returning something
    # that iterates like a query set of tagged objects.
    value = mock.MagicMock()
    value.select_related.return_value = tag_objects

    kww = KeywordsWidget()
    html = kww.render("any name", value)

    value.select_related.assert_called_once_with('tag')

    # Note:  Not a raw string so that the embedded single quotes are easier.
    regex = 'value=[\'"]%s[\'"]' % tag_string
    assert re.search(regex, html)


def test_keywords_form_field_uses_correct_widget():
    kwf = KeywordsField()
    assert isinstance(kwf.widget, KeywordsWidget)


def test_keywords_form_field_clean_good_data(tag_string, tag_list):
    kwf = KeywordsField()
    data = kwf.clean(tag_string)
    assert data == tag_list


def test_keywords_form_field_clean_repeated_semicolons(tag_string, tag_list):
    kwf = KeywordsField()

    # Repeated a semicolon
    first, semicolon, remainder = tag_string.partition(';')
    modified = first + semicolon + semicolon + remainder

    # Add a trailing semicolon, not repeated
    modified += semicolon

    data = kwf.clean(modified)
    assert data == tag_list


def test_keywords_form_field_clean_unsorted(tag_list):
    unsorted_string = '; '.join(reversed(tag_list))
    kwf = KeywordsField()
    data = kwf.clean(unsorted_string)
    assert data == tag_list


def test_keywords_form_field_clean_required():
    kwf = KeywordsField()
    with pytest.raises(ValidationError):
        kwf.clean('')


def test_keywords_form_field_clean_none():
    kwf = KeywordsField(required=False)
    data = kwf.clean(None)
    assert data == []


def test_keywords_form_field_clean_empty_string():
    kwf = KeywordsField(required=False)
    data = kwf.clean('')
    assert data == []


def test_keywords_form_field_clean_bad_chars():
    kwf = KeywordsField()
    for c in KeywordsField._NOT_ALLOWED:
        with pytest.raises(ValidationError):
            kwf.clean(c)


@pytest.mark.parametrize('form_class', [StoryRevisionForm,
                                        StoryCreditRevisionForm,
                                        StoryCharacterRevisionForm,
                                        StoryGroupRevisionForm])
def test_story_autocomplete_selects_span_the_cell(form_class):
    """
    The plain select shows until Select2 replaces it on page load, so it
    spans the cell instead of the browser's default width. Select2 copies
    these classes to its box, which input.css already sizes, so lg:w-4/5
    would make the box narrower than the other fields.
    """
    select2_widgets = (autocomplete.ModelSelect2,
                       autocomplete.ModelSelect2Multiple)
    wrong_width = []
    for name, field in form_class.base_fields.items():
        if isinstance(field.widget, select2_widgets):
            classes = field.widget.attrs.get('class', '').split()
            if 'w-full' not in classes or 'lg:w-4/5' in classes:
                wrong_width.append(name)
    assert wrong_width == []
