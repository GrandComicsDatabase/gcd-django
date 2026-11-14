# -*- coding: utf-8 -*-
"""Tests of the no answers and of the summary of an advanced search."""

from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict
from django.test import RequestFactory

from apps.gcd.models import Issue, Publisher, Series
from apps.gcd.views.search import do_advanced_search, used_search
from apps.stddata.models import Country, Language


def _terms(query):
    """Return the terms listed for the fields of the query string."""
    values = QueryDict('target=issue&method=icontains&%s' % query,
                       mutable=True)
    return used_search(values)[3]


def _issues_found(**fields):
    """Return the ids of the issues found by an advanced search."""
    request = RequestFactory().get('/search/advanced/process/', dict(
        {'target': 'issue', 'method': 'icontains'}, **fields))
    request.user = AnonymousUser()
    items, _target = do_advanced_search(request)
    return set(items.values_list('id', flat=True))


def test_a_no_answer_is_listed():
    """A filter answered with no is applied, so it is among the terms."""
    assert _terms('is_variant=False') == [('is_variant', 'False')]


def test_a_yes_answer_is_listed():
    """A filter answered with yes stays among the terms."""
    assert _terms('is_variant=True') == [('is_variant', 'True')]


def test_a_field_left_empty_is_not_listed():
    """Neither an empty field nor an empty choice is a search term."""
    assert _terms('title=&is_variant=None') == []


def test_the_summary_says_what_was_searched_for(client, db):
    """The list of terms opens with the kind of object searched for."""
    response = client.get('/search/advanced/process/', {
        'target': 'issue', 'method': 'icontains', 'series': 'absent'})
    assert 'Advanced search for Issues with' in response.content.decode()


def test_is_surrogate_answered_with_no_is_applied(db):
    """The no leaves out the issues of the surrogate indicia publishers."""
    country = Country.objects.get_or_create(
        code='zu', defaults={'name': 'Testland U'})[0]
    language = Language.objects.get_or_create(
        code='zu', defaults={'name': 'Testish U'})[0]
    publisher = Publisher.objects.create(name='Test Publisher',
                                         country=country, year_began=1950)
    series = Series.objects.create(
        name='Surrogate Test', sort_name='Surrogate Test', year_began=1950,
        country=country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1950')
    issues = {}
    for surrogate in (True, False):
        indicia = publisher.indiciapublisher_set.create(
            name='Indicia %s' % surrogate, country=country,
            is_surrogate=surrogate)
        issues[surrogate] = Issue.objects.create(
            number=str(surrogate), series=series, sort_code=int(surrogate),
            indicia_publisher=indicia)

    assert _issues_found(series='Surrogate Test', is_surrogate='False') == {
        issues[False].id}
    assert _issues_found(series='Surrogate Test', is_surrogate='True') == {
        issues[True].id}
