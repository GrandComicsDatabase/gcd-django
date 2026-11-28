"""My Comics tells the collector which issues of a collection were deleted."""
import importlib

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import clear_url_caches, reverse

from apps.gcd.models import Issue, Publisher, Series
from apps.indexer.models import Indexer
from apps.mycomics import urls as mycomics_urls
from apps.mycomics.models import CollectionItem, Collector, \
                                 ConditionGradeScale
from apps.stddata.models import Country, Language

COLLECTION_NOTICE = 'These issues of the collection were deleted from the GCD:'
ITEM_NOTICE = 'This issue was deleted from the GCD.'


def _reload_urls():
    """Builds the url patterns again from the current settings."""
    importlib.reload(mycomics_urls)
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    clear_url_caches()


@pytest.fixture
def mycomics_site():
    """All the pages of My Comics exist only with MYCOMICS = True."""
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield
    _reload_urls()


@pytest.fixture
def items(db, client, mycomics_site):
    """A live and a deleted issue in a collection of the logged-in owner."""
    country = Country.objects.get_or_create(
      id=931, defaults={'code': 'n1', 'name': 'Testland N'})[0]
    language = Language.objects.get_or_create(
      id=931, defaults={'code': 'n1', 'name': 'Testish N'})[0]
    publisher = Publisher.objects.create(
      name='Some Publisher', country=country, year_began=1990)
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, publisher=publisher,
      is_comics_publication=True, publication_dates='1990')
    user = User.objects.create_user('some.collector')
    Indexer.objects.create(user=user, country=country)
    Collector.objects.create_collector(
      user, grade_system=ConditionGradeScale.objects.create(name='Some Scale'),
      default_language=language)
    collection = user.collector.default_have_collection
    items = {}
    for number, name in enumerate(('live', 'deleted'), start=1):
        items[name] = CollectionItem.objects.create(
          issue=Issue.objects.create(
            number=str(number), series=series, sort_code=number,
            publication_date='1990', key_date='1990-01-00',
            deleted=name == 'deleted'))
        items[name].collections.add(collection)
    client.force_login(user)
    return items


def _page(client, view, item=None):
    collection = Collector.objects.get().default_have_collection
    kwargs = {'collection_id': collection.id}
    if item:
        kwargs['item_id'] = item.id
    response = client.get(reverse(view, kwargs=kwargs))
    assert response.status_code == 200
    return response.content.decode()


def _item_link(item):
    return '<a href="%s">%s</a>' % (
      reverse('view_item', kwargs={'item_id': item.id,
                                   'collection_id': item.collections.get().id}),
      item.issue.full_name())


def test_collection_page_lists_its_deleted_issues(client, items):
    page = _page(client, 'view_collection')
    notice = page[page.index(COLLECTION_NOTICE):]
    notice = notice[:notice.index('</div>')]
    assert _item_link(items['deleted']) in notice
    assert _item_link(items['live']) not in notice

    Issue.objects.filter(deleted=True).update(deleted=False)
    assert COLLECTION_NOTICE not in _page(client, 'view_collection')


def test_item_page_says_its_issue_was_deleted(client, items):
    page = _page(client, 'view_item', items['deleted'])
    history = reverse('change_history', kwargs={
      'model_name': 'issue', 'id': items['deleted'].issue.id})
    assert ITEM_NOTICE in page
    assert 'href="%s"' % history in page

    assert ITEM_NOTICE not in _page(client, 'view_item', items['live'])


def test_the_notice_reads_the_publishers_with_the_items(
      client, items, django_assert_num_queries):
    collection = Collector.objects.get().default_have_collection
    response = client.get(reverse('view_collection',
                                  kwargs={'collection_id': collection.id}))
    deleted = list(response.context['deleted_items'])

    with django_assert_num_queries(0):
        assert [item.issue.series.publisher.name for item in deleted] == [
          'Some Publisher']
