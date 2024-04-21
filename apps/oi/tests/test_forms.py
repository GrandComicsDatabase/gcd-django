# -*- coding: utf-8 -*-


import re
import mock
import pytest

from django.forms import ValidationError

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
