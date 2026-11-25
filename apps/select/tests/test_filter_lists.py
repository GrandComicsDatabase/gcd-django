"""Tests of the filter forms of the issue and sequence lists."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import Issue, Publisher, Series, Story, StoryType
from apps.select.views import filter_issues, filter_sequences
from apps.stddata.models import Country, Language

LISTS = [(filter_issues, Issue, 'gcd_issue'),
         (filter_sequences, Story, 'gcd_story')]
FIELDS = {'publisher', 'country', 'language'}


@pytest.fixture
def one_sequence(db):
    """Return a sequence in an issue of a series, with what they need."""
    country, _ = Country.objects.get_or_create(
        code='zz', defaults={'name': 'Test country'})
    language, _ = Language.objects.get_or_create(
        code='zz', defaults={'name': 'Test language'})
    publisher = Publisher.objects.create(
        name='Test publisher', country=country, year_began=1991)
    series = Series.objects.create(
        name='Test series', sort_name='Test series', publisher=publisher,
        country=country, language=language, year_began=1991)
    issue = Issue.objects.create(series=series, number='1', sort_code=1)
    story_type, _ = StoryType.objects.get_or_create(
        name='filter-test', defaults={'sort_code': 99060})
    return Story.objects.create(issue=issue, type=story_type,
                                sequence_number=0)


def run_filter(function, objects, table):
    """Filter objects as a list page does.

    Return the names of the form fields and the queries that read whole
    rows of the table, recognised by its ``created`` column.
    """
    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    with CaptureQueriesContext(connection) as queries:
        filter, _ = function(request, objects)
    rows = [q['sql'] for q in queries if f'`{table}`.`created`' in q['sql']]
    return set(filter.form.fields), rows


@pytest.mark.django_db
@pytest.mark.parametrize('function, model, table', LISTS)
def test_empty_list_drops_fields_and_reads_no_rows(function, model, table):
    """An empty list drops the publisher, country and language fields."""
    fields, rows = run_filter(function, model.objects.filter(pk__lt=0),
                              table)
    assert not FIELDS & fields
    assert rows == []


@pytest.mark.parametrize('function, model, table', LISTS)
def test_list_keeps_fields_and_reads_no_rows(one_sequence, function, model,
                                             table):
    """A list with rows keeps the fields and reads none of its rows."""
    fields, rows = run_filter(function, model.objects.all(), table)
    assert FIELDS <= fields
    assert rows == []
