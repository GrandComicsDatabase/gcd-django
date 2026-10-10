"""Regression coverage for catalog-sized homepage and series searches."""

from datetime import datetime

import pytest
from django.db import connection
from django.db.models import Q
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import (
    Creator, CreatorNameDetail, CreditType, Issue, Publisher, Series,
    Story, StoryCredit, StoryType,
)
from apps.gcd.views import index
from apps.gcd.views import search
from apps.stddata.models import Country, Date, Language, Script


@pytest.mark.django_db
def test_homepage_does_not_query_hidden_timeline(client, settings):
    settings.USE_TEMPLATESADMIN = False
    with CaptureQueriesContext(connection) as queries:
        response = client.get('/')
    assert response.status_code == 200
    assert not any('gcd_creator' in q['sql'] for q in queries)


@pytest.mark.django_db
def test_homepage_still_loads_enabled_timeline(
        settings, monkeypatch, series_catalog):
    settings.USE_TEMPLATESADMIN = True
    today = datetime.today()
    birthday = Date.objects.create(year='1970', month=f'{today.month:02}',
                                   day=f'{today.day:02}')
    script, _ = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    story_type, _ = StoryType.objects.get_or_create(
        name='timeline-test', defaults={'sort_code': 99050})
    credit_type, _ = CreditType.objects.get_or_create(
        name='timeline-test', defaults={'sort_code': 99050})
    creators = []
    names = []
    for label in ['Eleven issues', 'Ten issues']:
        creator = Creator.objects.create(
            gcd_official_name=label, sort_name=label,
            birth_date=birthday, bio='Timeline biography')
        creators.append(creator)
        names.append(CreatorNameDetail.objects.create(
            name=label, creator=creator, in_script=script))
    series = Series.objects.get(pk=min(series_catalog))
    for number in range(11):
        issue = Issue.objects.create(series=series, number=str(number + 10),
                                     sort_code=number + 10)
        story = Story.objects.create(issue=issue, type=story_type,
                                     sequence_number=0)
        StoryCredit.objects.create(story=story, creator=names[0],
                                   credit_type=credit_type)
        if number < 10:
            StoryCredit.objects.create(story=story, creator=names[1],
                                       credit_type=credit_type)
    request = RequestFactory().get('/')
    request.LANGUAGE_CODE = 'en'
    monkeypatch.setattr('apps.gcd.views.render',
                        lambda request, template, context: context)
    with CaptureQueriesContext(connection) as queries:
        context = index(request)
    assert creators[0].pk in {c.pk for c in context['creators']}
    assert creators[1].pk not in {c.pk for c in context['creators']}
    assert next(c for c in context['creators']
                if c.pk == creators[0].pk).issue_count == 11
    assert any('gcd_creator' in q['sql'] for q in queries)


@pytest.fixture
def series_catalog(db):
    country, _ = Country.objects.get_or_create(
        code='zz', defaults={'name': 'Test country'})
    language, _ = Language.objects.get_or_create(
        code='zz', defaults={'name': 'Test language'})
    publisher = Publisher.objects.create(
        name='Test publisher', country=country, year_began=1991)

    def make_series(name, deleted=False):
        return Series.objects.create(
            name=name, sort_name=name, publisher=publisher,
            country=country, language=language, year_began=1991,
            deleted=deleted)

    named = make_series('Nathan Never')
    title_only = make_series('Specials')
    empty = make_series('Nathan Never without issues')
    deleted = make_series('Nathan Never deleted', deleted=True)
    unrelated = make_series('Unrelated')
    for series, titles in [
            (named, ['Nathan Never', 'Other']),
            (title_only, ['Nathan Never special', 'Nathan Never extra']),
            (deleted, ['Nathan Never']), (unrelated, ['Other'])]:
        for number, title in enumerate(titles, 1):
            Issue.objects.create(series=series, number=str(number),
                                 sort_code=number, title=title)
    return {named.pk, title_only.pk, empty.pk}


@pytest.mark.parametrize('term', ['nAtHaN nEvEr', 'special', '', 'no match'])
def test_series_search_preserves_matches_without_duplicates(
        series_catalog, term, settings, monkeypatch):
    settings.USE_ELASTICSEARCH = False

    def capture(request, name, q_obj, sort, class_, template, **kwargs):
        return kwargs['things']

    monkeypatch.setattr(search, 'generic_by_name', capture)
    results = search.series_by_name(RequestFactory().get('/'), term)
    ids = list(results.values_list('pk', flat=True))
    previous = Series.objects.exclude(deleted=True).filter(
        Q(name__icontains=term) | Q(issue__title__icontains=term))
    assert set(ids) == set(previous.values_list('pk', flat=True))
    assert len(ids) == len(set(ids))
    if term == 'nAtHaN nEvEr':
        assert set(ids) == series_catalog


@pytest.mark.parametrize('count, removed', [(3, 0), (3, 1), (3, 2), (1, 0)])
def test_issue_deletion_updates_series_endpoints(series_catalog, count, removed):
    series = Series.objects.get(name='Nathan Never without issues')
    issues = [Issue.objects.create(series=series, number=str(i), sort_code=i)
              for i in range(count)]
    series.set_first_last_issues()
    issues[removed].delete()
    # A later save of the cached parent must not restore stale endpoints.
    issues[removed].series.save()
    series.refresh_from_db()
    remaining = [issue for issue in issues if not issue.deleted]
    assert series.first_issue == (remaining[0] if remaining else None)
    assert series.last_issue == (remaining[-1] if remaining else None)
    assert Issue.objects.get(pk=issues[removed].pk).deleted


def test_publication_dates_keep_available_issue_dates():
    series = Series(issue_count=2, year_began=1991, year_ended=2001,
                    first_issue=Issue(publication_date='April 1991'),
                    last_issue=Issue(publication_date='March 2001'))
    assert series.display_publication_dates() == 'April 1991 - March 2001'


def test_series_search_page_with_issue_dates(
        series_catalog, client, settings):
    settings.USE_ELASTICSEARCH = False
    for series in Series.objects.filter(pk__in=series_catalog):
        series.issue_count = series.active_issues().count()
        series.set_first_last_issues()
    response = client.get('/series/name/Nathan%20Never/')
    assert response.status_code == 200
    assert b'Nathan Never' in response.content
