# -*- coding: utf-8 -*-
"""Tests of the list of terms shown with the results of an advanced search."""

from django.http import QueryDict

from apps.gcd.views.search import used_search


def _terms(query):
    """Return the terms listed for the fields of the query string."""
    values = QueryDict('target=issue&method=icontains&%s' % query,
                       mutable=True)
    return used_search(values)[3]


def test_a_no_answer_is_listed():
    """A filter answered with no is applied, so it is among the terms."""
    assert _terms('is_variant=False') == [('is_variant', 'False')]


def test_a_yes_answer_is_listed():
    """A filter answered with yes stays among the terms."""
    assert _terms('is_variant=True') == [('is_variant', 'True')]


def test_a_field_left_empty_is_not_listed():
    """Neither an empty field nor an empty choice is a search term."""
    assert _terms('title=&is_variant=None') == []
