"""Only the owner of a collection gets its editing controls."""
import importlib

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
def collection(db):
    """On My Comics, a public collection of one item and another collector."""
    country = Country.objects.get_or_create(
      id=946, defaults={'code': 'o6', 'name': 'Testland O'})[0]
    language = Language.objects.get_or_create(
      id=946, defaults={'code': 'o6', 'name': 'Testish O'})[0]
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      publisher=Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1990),
      publication_dates='1990')
    scale = ConditionGradeScale.objects.create(name='Some Scale')
    for name in ('owner', 'visitor'):
        user = User.objects.create_user(name)
        Indexer.objects.create(user=user, country=country)
        Collector.objects.create_collector(user, grade_system=scale,
                                           default_language=language)
    collection = User.objects.get(
      username='owner').collector.default_have_collection
    collection.public = True
    collection.save()
    CollectionItem.objects.create(issue=Issue.objects.create(
      number='1', series=series, sort_code=1, publication_date='1990',
      key_date='1990-01-00')).collections.add(collection)
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield collection
    _reload_urls()


def _owner_controls(client, collection):
    """The owner-only controls that the collection page shows."""
    kwargs = {'collection_id': collection.id}
    response = client.get(reverse('view_collection', kwargs=kwargs))
    assert response.status_code == 200
    page = response.content.decode()
    controls = {
      'Edit Shown Items': reverse('edit_collection_items', kwargs=kwargs),
      'remove item': 'id="remove-item-%d"' % collection.items.get().id}
    return {name for name, mark in controls.items() if mark in page}


@pytest.mark.parametrize('username', ['visitor', None],
                         ids=['other collector', 'anonymous'])
def test_visitor_of_a_public_collection_gets_no_owner_controls(
  client, collection, username):
    """Another collector or an anonymous visitor gets neither control."""
    if username:
        client.force_login(User.objects.get(username=username))
    assert _owner_controls(client, collection) == set()


def test_owner_gets_the_controls(client, collection):
    """The owner still gets Edit Shown Items and the remove button."""
    client.force_login(collection.collector.user)
    assert _owner_controls(client, collection) == {
      'Edit Shown Items', 'remove item'}
