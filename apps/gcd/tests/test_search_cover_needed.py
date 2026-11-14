import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.stddata.models import Country, Language
from apps.gcd.models import Cover, Issue, Publisher, Series
from apps.gcd.views.search import do_advanced_search


def cover_needed_search(target):
    request = RequestFactory().get(
        '/search/advanced/process/',
        {'target': target, 'method': 'icontains', 'cover_needed': 'on'})
    request.user = AnonymousUser()
    items, _target = do_advanced_search(request)
    return set(items.values_list('id', flat=True))


@pytest.fixture
def publisher(db):
    country = Country.objects.get_or_create(
        id=903, defaults={'code': 'zc', 'name': 'Testland C'})[0]
    return Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1990)


def _issues(publisher, name, *issue_covers):
    """A series with one issue per entry, each with the given covers."""
    language = Language.objects.get_or_create(
        id=903, defaults={'code': 'zc', 'name': 'Testish C'})[0]
    series = Series.objects.create(
        name=name, sort_name=name, year_began=1990,
        country=publisher.country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=True,
        publication_dates='1990')
    issues = []
    for number, covers in enumerate(issue_covers, 1):
        issue = Issue.objects.create(
            number=str(number), series=series, sort_code=number,
            publication_date='1990', key_date='1990-01-00')
        for cover in covers:
            Cover.objects.create(issue=issue, deleted=cover == 'deleted',
                                 marked=cover == 'marked')
        issues.append(issue)
    return issues


@pytest.mark.parametrize('target', ['issue', 'series'])
def test_cover_needed_ignores_deleted_covers(publisher, target):
    needed = (_issues(publisher, 'No Cover', ()) +
              _issues(publisher, 'Only Deleted', ('deleted',)) +
              _issues(publisher, 'Marked', ('marked',)))
    _issues(publisher, 'Active', ('active',))
    _issues(publisher, 'Deleted And Replaced', ('deleted', 'active'))
    needed += _issues(publisher, 'Mixed', ('active',), ('deleted',))[1:]

    if target == 'issue':
        expected = {issue.id for issue in needed}
    else:
        expected = {issue.series_id for issue in needed}
    assert cover_needed_search(target) == expected
