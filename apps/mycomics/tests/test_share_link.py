"""A My Comics collection is read by whoever has its secret link."""
import importlib
import re
import secrets
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
def data(db):
    """On My Comics an owner has a private want list with 2 items and a
    private have collection; another user has a collection of his own."""
    country = Country.objects.get_or_create(
      id=937, defaults={'code': 'n7', 'name': 'Testland S'})[0]
    language = Language.objects.get_or_create(
      id=937, defaults={'code': 'n7', 'name': 'Testish S'})[0]
    series = Series.objects.create(
      name='Shared Series', sort_name='Shared Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      publisher=Publisher.objects.create(
        name='Some Publisher', country=country, year_began=1990),
      publication_dates='1990')
    scale = ConditionGradeScale.objects.create(name='Some Scale')
    data = SimpleNamespace()
    for name in ('owner', 'reader'):
        user = User.objects.create_user(name)
        Indexer.objects.create(user=user, country=country)
        Collector.objects.create_collector(user, grade_system=scale,
                                           default_language=language)
        setattr(data, name, user)
    data.want = data.owner.collector.default_want_collection
    data.have = data.owner.collector.default_have_collection
    data.items = []
    for number in (1, 2):
        item = CollectionItem.objects.create(
          own=False, issue=Issue.objects.create(
            number=str(number), series=series, sort_code=number,
            publication_date='1990', key_date='1990-01-00'))
        item.collections.add(data.want)
        data.items.append(item)
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield data
    _reload_urls()


def _share(collection):
    """Gives the collection a key, as the collection form does."""
    collection.share_key = secrets.token_urlsafe(32)
    collection.save()
    return collection.share_key


def _collection_url(collection, key=None):
    """The address of the collection page, with the key if given."""
    url = reverse('view_collection', kwargs={'collection_id': collection.id})
    return url if key is None else '%s?key=%s' % (url, key)


def _item_url(item, collection, key=None):
    """The address of the item page, with the key if given."""
    url = reverse('view_item', kwargs={'item_id': item.id,
                                       'collection_id': collection.id})
    return url if key is None else '%s?key=%s' % (url, key)


def _save_form(client, collection, shared, **fields):
    """Saves the form of the collection, with its secret link box checked
    or not."""
    post = {'name': collection.name, **fields}
    if shared:
        post['shared'] = 'on'
    response = client.post(
      reverse('edit_collection', kwargs={'collection_id': collection.id}),
      post)
    assert response.status_code == 302
    collection.refresh_from_db()
    return collection.share_key


def test_owner_creates_and_withdraws_the_secret_link(client, data):
    """The box of the form creates a key, keeps it while checked and drops
    it when unchecked; the old link then gives 404, a new one works."""
    want = data.want
    client.force_login(data.owner)
    edit_url = reverse('edit_collection', kwargs={'collection_id': want.id})
    box = re.compile(r'<input type="checkbox" name="shared"[^>]*>')
    assert box.findall(client.get(edit_url).content.decode()) == [
      '<input type="checkbox" name="shared" class="" '
      'aria-describedby="id_shared_helptext" id="id_shared">']
    assert 'id="share-url"' not in client.get(
      _collection_url(want)).content.decode()

    key = _save_form(client, want, True, share_key='chosen')
    assert len(key) == 43
    page = client.get(_collection_url(want)).content.decode()
    assert 'id="share-url"' in page
    assert 'value="http://testserver%s"' % _collection_url(want, key) in page
    assert box.findall(client.get(edit_url).content.decode())[0].endswith(
      ' checked>')
    assert _save_form(client, want, True) == key

    assert _save_form(client, want, False) == ''
    assert 'id="share-url"' not in client.get(
      _collection_url(want)).content.decode()
    client.logout()
    assert client.get(_collection_url(want, key)).status_code == 404
    assert client.get(
      _item_url(data.items[0], want, key)).status_code == 404

    client.force_login(data.owner)
    new_key = _save_form(client, want, True)
    assert len(new_key) == 43 and new_key != key


@pytest.mark.parametrize('reader', [None, 'reader'])
def test_the_link_reads_the_collection_without_owner_controls(
  client, data, reader):
    """With the link a visitor, or another user, reads the collection and
    its items, the links keep the key, and no owner control shows."""
    want = data.want
    key = _share(want)
    if reader:
        client.force_login(getattr(data, reader))
    response = client.get(_collection_url(want, key))
    assert response.status_code == 200
    page = response.content.decode()
    for item in data.items:
        assert 'href="%s"' % _item_url(item, want, key) in page
    assert '<input type="hidden" name="key" value="%s">' % key in page
    for control in ('id="share-url"', 'Edit Shown Items', 'remove_issue(',
                    reverse('edit_collection',
                            kwargs={'collection_id': want.id}),
                    reverse('export_collection',
                            kwargs={'collection_id': want.id}),
                    reverse('edit_collection_items',
                            kwargs={'collection_id': want.id})):
        assert control not in page

    first, second = data.items
    response = client.get(_item_url(first, want, key))
    assert response.status_code == 200
    page = response.content.decode()
    assert 'href="%s"' % _item_url(second, want, key) in page
    assert 'href="%s?page=1&amp;key=%s"' % (_collection_url(want), key) \
        in page
    for control in ('Delete from collection', 'To other collection',
                    'href="#edit-item"', 'I want this comic.',
                    reverse('delete_item', kwargs={
                      'item_id': first.id, 'collection_id': want.id})):
        assert control not in page


@pytest.mark.parametrize('key', [
  'wrong', '', chr(233), 'withdrawn', 'of the have collection',
  'of the other collector'])
def test_a_wrong_or_withdrawn_key_gives_404(client, data, key):
    """Any key but the current one of the collection gives 404."""
    want = data.want
    if key == 'withdrawn':
        key = _share(want)
        want.share_key = ''
        want.save()
    else:
        _share(want)
    if key == 'of the have collection':
        key = _share(data.have)
    if key == 'of the other collector':
        key = _share(data.reader.collector.default_want_collection)
    for user in (None, data.reader):
        if user:
            client.force_login(user)
        assert client.get(_collection_url(want, key)).status_code == 404
        assert client.get(
          _item_url(data.items[0], want, key)).status_code == 404


def test_without_the_link_the_collection_reads_as_before(client, data):
    """Without the key a private collection still sends visitors to the
    login and refuses other users; a public one is read as before and its
    pages do not show the key."""
    want = data.want
    key = _share(want)
    response = client.get(_collection_url(want))
    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)
    client.force_login(data.reader)
    assert client.get(_collection_url(want)).status_code == 403
    assert client.get(_item_url(data.items[0], want)).status_code == 403

    want.public = True
    want.save()
    for user in (None, data.reader):
        client.logout()
        if user:
            client.force_login(user)
        assert client.get(_collection_url(want, key)).status_code == 200
        for url in (_collection_url(want), _collection_url(want, 'wrong'),
                    _item_url(data.items[0], want)):
            response = client.get(url)
            assert response.status_code == 200
            assert key not in response.content.decode()
    client.force_login(data.owner)
    page = client.get(_collection_url(want)).content.decode()
    assert 'value="http://testserver%s"' % _collection_url(want, key) in page
