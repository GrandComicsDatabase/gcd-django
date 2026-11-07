"""Entry to the bulk issue edit from the advanced search."""
import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.mycomics.models import Collector, ConditionGradeScale

SEARCH = {'target': 'issue', 'method': 'icontains', 'logic': 'False'}


@pytest.fixture
def searching_indexer(any_indexer, any_language):
    """An indexer with the collector a confirmed account gets."""
    Collector.objects.create_collector(
      any_indexer,
      grade_system=ConditionGradeScale.objects.create(name='Test scale'),
      default_language=any_language)
    return any_indexer


def _allow_reserving(user):
    """Give a test indexer the permission to reserve changes."""
    user.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))


@pytest.mark.django_db
def test_bulk_edit_of_empty_search_redirects(client, searching_indexer):
    """A search without results goes back to the search, not to an error."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)

    response = client.get(reverse('edit_issues_in_bulk'),
                          dict(SEARCH, series='No Such Series'))

    assert response.status_code == 302
    assert response['Location'].startswith(
      reverse('process_advanced_search'))


@pytest.mark.django_db
@pytest.mark.parametrize('method, query', [('get', ''), ('post', ''),
                                           ('post', '?target=series')])
def test_bulk_edit_without_issue_target_redirects(client, searching_indexer,
                                                  method, query):
    """A request without the issue target goes back to the search."""
    _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)

    response = getattr(client, method)(reverse('edit_issues_in_bulk') + query)

    assert response.status_code == 302
    assert response['Location'].startswith(
      reverse('process_advanced_search'))


@pytest.mark.django_db
@pytest.mark.parametrize('series, can_reserve, shown', [
    ('Series for Issues', True, True),
    ('Series for Issues', False, False),
    ('No Such Series', True, False),
])
def test_bulk_change_link_on_issue_search(client, any_added_issue,
                                          searching_indexer, series,
                                          can_reserve, shown):
    """The link needs results and the permission the bulk edit needs."""
    if can_reserve:
        _allow_reserving(searching_indexer)
    client.force_login(searching_indexer)

    response = client.get(reverse('process_advanced_search'),
                          dict(SEARCH, series=series))

    assert response.status_code == 200
    content = response.content.decode()
    assert (reverse('edit_issues_in_bulk') in content) is shown
