"""My Comics moves or deletes the selected items of a collection at once."""
import importlib
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import clear_url_caches, reverse

from apps.gcd.models import Issue, Publisher, Series
from apps.indexer.models import Indexer
from apps.mycomics import urls as mycomics_urls
from apps.mycomics.models import CollectionItem, Collector, ConditionGradeScale
from apps.stddata.models import Country, Language


def _reload_urls():
    """Builds the url patterns again from the current settings."""
    importlib.reload(mycomics_urls)
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    clear_url_caches()


@pytest.fixture
def data(db, client):
    """On My Comics the logged-in owner has 3 items, another collector 1."""
    country = Country.objects.get_or_create(
      id=936, defaults={'code': 'n6', 'name': 'Testland M'})[0]
    language = Language.objects.get_or_create(
      id=936, defaults={'code': 'n6', 'name': 'Testish M'})[0]
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      publisher=Publisher.objects.create(
        name='Some Publisher', country=country, year_began=1990),
      publication_dates='1990')
    scale = ConditionGradeScale.objects.create(name='Some Scale')
    data = SimpleNamespace()
    for prefix in ('', 'other_'):
        user = User.objects.create_user(prefix + 'collector')
        Indexer.objects.create(user=user, country=country)
        Collector.objects.create_collector(user, grade_system=scale,
                                           default_language=language)
        setattr(data, prefix + 'have', user.collector.default_have_collection)
        setattr(data, prefix + 'want', user.collector.default_want_collection)
    for number, name in enumerate(('first', 'second', 'third', 'foreign')):
        item = CollectionItem.objects.create(
          own=True, issue=Issue.objects.create(
            number=str(number), series=series, sort_code=number,
            publication_date='1990', key_date='1990-01-00'))
        item.collections.add(data.other_have if number == 3 else data.have)
        setattr(data, name, item)
    client.force_login(data.have.collector.user)
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield data
    _reload_urls()


def _url(view, collection):
    return reverse(view, kwargs={'collection_id': collection.id})


def _post(client, source, action, items, method='post', **fields):
    return getattr(client, method)(
      _url('move_or_delete_items', source) + '?page=2',
      {'action': action, 'items': [getattr(i, 'id', i) for i in items],
       **fields})


def test_collection_page_offers_the_selection_to_its_owner(client, data):
    have = data.have
    page = client.get(_url('view_collection', have) + '?page=1')
    page = page.content.decode()
    assert 'action="%s?page=1"' % _url('move_or_delete_items', have) in page
    for item in have.items.all():
        assert 'name="items" value="%d"' % item.id in page

    have.public = True
    have.save()
    client.force_login(data.other_have.collector.user)
    page = client.get(_url('view_collection', have)).content.decode()
    assert 'name="items"' not in page


def test_selected_items_move_or_leave_the_collection(client, data):
    data.want.own_used, data.want.own_default = True, False
    data.want.save()
    response = _post(client, data.have, 'move', [data.first, data.second],
                     collection=data.want.id)
    assert response.url == _url('view_collection', data.have) + '?page=2'
    assert list(data.have.items.all()) == [data.third]
    assert [(i, i.own) for i in data.want.items.all()] == [
      (data.first, False), (data.second, False)]

    data.first.collections.add(data.have)
    _post(client, data.want, 'delete', [data.first, data.second])
    assert list(data.have.items.all()) == [data.first, data.third]
    assert not data.want.items.exists()
    assert not CollectionItem.objects.filter(id=data.second.id).exists()


@pytest.mark.parametrize('method, source, action, items, target, status', [
  ('post', 'have', 'move', ['first', 'foreign'], 'other_want', 302),
  ('post', 'have', 'move', ['first'], 'have', 302),
  ('post', 'have', 'delete', ['foreign'], 'want', 302),
  ('post', 'have', 'delete', [], 'want', 302),
  ('post', 'have', 'delete', ['x', chr(178)], 'want', 302),
  ('post', 'other_have', 'delete', ['foreign'], 'want', 404),
  ('get', 'have', 'delete', ['first'], 'want', 200)])
def test_refused_requests_change_nothing(client, data, method, source,
                                         action, items, target, status):
    response = _post(client, getattr(data, source), action,
                     [getattr(data, i, i) for i in items], method,
                     collection=getattr(data, target).id)
    assert response.status_code == status
    assert data.have.items.count() == 3
    assert list(data.other_have.items.all()) == [data.foreign]
    assert not data.other_want.items.exists()
