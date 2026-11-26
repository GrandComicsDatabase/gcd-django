"""
My Comics shows its messages about collections, items, subscriptions and
reading lists in the language of the page when a translation exists.
"""
import importlib

import polib
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import clear_url_caches, reverse

from apps.gcd.models import Issue, Publisher, Series
from apps.indexer.models import Indexer
from apps.mycomics import urls as mycomics_urls
from apps.mycomics.models import Collection, CollectionItem, Collector, \
                                 ConditionGradeScale, ReadingOrder, \
                                 ReadingOrderItem
from apps.stddata.models import Country, Language

# The messages as their msgids in the message files, with test translations.
OWN_WANT = ('Item status for own/want differed from default of new '
            'collection <b>%s</b> and was changed.')
FOR_SALE = ('Item status is set to for sale due to default of new '
            'collection <b>%s</b>.')
GERMAN = {
    'Collection <b>%s</b> deleted.': 'Sammlung <b>%s</b> geloescht.',
    'Item <b>%s</b> removed from %s': 'Eintrag <b>%s</b> aus %s entfernt',
    OWN_WANT: 'Besitzstatus nach der neuen Sammlung <b>%s</b> geaendert.',
    FOR_SALE: 'Nach der neuen Sammlung <b>%s</b> zum Verkauf gestellt.',
    '%s is already subscribed for the collection %s.':
        '%s ist fuer die Sammlung %s schon abonniert.',
    'Series %s is now subscribed for the collection %s.':
        'Serie %s ist jetzt fuer die Sammlung %s abonniert.',
    'Reading Order <b>%s</b> deleted.': 'Leseliste <b>%s</b> geloescht.',
    'Item %s saved.': 'Eintrag %s gespeichert.',
    'Item <b>%s</b> removed from Reading List %s':
        'Eintrag <b>%s</b> aus der Leseliste %s entfernt',
}


def _reload_urls():
    """Builds the url patterns again from the current settings."""
    importlib.reload(mycomics_urls)
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    clear_url_caches()


@pytest.fixture
def german(settings, tmp_path):
    """
    The German message file holds the test translations; a page asked with
    ?lang=de uses it.
    """
    catalog = polib.POFile()
    catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8'}
    for msgid, msgstr in GERMAN.items():
        catalog.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    folder = tmp_path / 'de' / 'LC_MESSAGES'
    folder.mkdir(parents=True)
    catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]


@pytest.fixture
def data(db, client, german):
    """
    The logged-in collector has an issue in the default have collection, a
    second collection and a reading list with the same issue, all on My
    Comics.
    """
    country = Country.objects.get_or_create(
      id=941, defaults={'code': 'n7', 'name': 'Testland T'})[0]
    language = Language.objects.get_or_create(
      id=941, defaults={'code': 'n7', 'name': 'Testish T'})[0]
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      is_current=True, publication_dates='1990',
      publisher=Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1990))
    issue = Issue.objects.create(number='1', series=series, sort_code=1,
                                 publication_date='1990',
                                 key_date='1990-01-00')
    user = User.objects.create_user('some.collector')
    Indexer.objects.create(user=user, country=country)
    Collector.objects.create_collector(
      user, default_language=language,
      grade_system=ConditionGradeScale.objects.create(name='Some Scale'))
    collector = user.collector
    item = CollectionItem.objects.create(issue=issue, own=True)
    item.collections.add(collector.default_have_collection)
    reading_order = ReadingOrder.objects.create(collector=collector,
                                                name='Some Reading List')
    client.force_login(user)
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield {'series': series, 'item': item,
               'have': collector.default_have_collection,
               'other': Collection.objects.create(collector=collector,
                                                  name='Some Collection'),
               'reading_order': reading_order,
               'reading_item': ReadingOrderItem.objects.create(
                 issue=issue, reading_order=reading_order,
                 sequence_number=1)}
    _reload_urls()


def _post(client, name, data=None, lang='de', **kwargs):
    """Posts to the named page in the language, gives the messages back."""
    response = client.post(reverse(name, kwargs=kwargs) + '?lang=' + lang,
                           data or {})
    assert response.status_code in (200, 302)
    return [str(message) for message in get_messages(response.wsgi_request)]


def test_deleted_collection(client, data):
    """The message names the deleted collection."""
    assert _post(client, 'delete_collection',
                 collection_id=data['other'].id) == [
      'Sammlung <b>Some Collection</b> geloescht.']


def test_item_removed_from_collection(client, data):
    """The message names the issue and the collection it left."""
    issue = data['item'].issue.full_name()

    assert _post(client, 'delete_item', item_id=data['item'].id,
                 collection_id=data['have'].id) == [
      'Eintrag <b>%s</b> aus Default have collection entfernt' % issue]


def test_item_moved_to_a_collection_with_other_defaults(client, data):
    """The warnings name the collection whose defaults the item took."""
    Collection.objects.filter(id=data['other'].id).update(
      own_used=True, own_default=False, for_sale_used=True,
      for_sale_default=True)

    shown = _post(client, 'move_item',
                  {'collection': data['other'].id, 'move': 'Move'},
                  item_id=data['item'].id, collection_id=data['have'].id)

    assert 'Besitzstatus nach der neuen Sammlung <b>Some Collection</b> ' \
           'geaendert.' in shown
    assert 'Nach der neuen Sammlung <b>Some Collection</b> zum Verkauf ' \
           'gestellt.' in shown


def test_item_copied_to_a_collection_for_sale(client, data):
    """The warning names the collection that put the item for sale."""
    Collection.objects.filter(id=data['other'].id).update(
      for_sale_used=True, for_sale_default=True)

    assert 'Nach der neuen Sammlung <b>Some Collection</b> zum Verkauf ' \
           'gestellt.' in _post(client, 'move_item',
                                {'collection': data['other'].id,
                                 'copy': 'Copy'},
                                item_id=data['item'].id,
                                collection_id=data['have'].id)


@pytest.mark.parametrize('lang, first, second', [
  ('de', 'Serie %s ist jetzt fuer die Sammlung %s abonniert.',
   '%s ist fuer die Sammlung %s schon abonniert.'),
  ('en', 'Series %s is now subscribed for the collection %s.',
   '%s is already subscribed for the collection %s.')], ids=['de', 'en'])
def test_series_subscribed(client, data, lang, first, second):
    """A first and a second subscription, in German and in English."""
    names = (data['series'], data['have'])
    # The messages of a page not shown yet stay: the last one is the new one.
    shown = [_post(client, 'series_subscribe',
                   {'collection_id': data['have'].id}, lang=lang,
                   series_id=data['series'].id)[-1] for _ in range(2)]

    assert shown == [first % names, second % names]


def test_deleted_reading_list(client, data):
    """The message names the deleted reading list."""
    assert _post(client, 'delete_reading_order',
                 reading_order_id=data['reading_order'].id) == [
      'Leseliste <b>Some Reading List</b> geloescht.']


def test_reading_list_item_saved(client, data):
    """The message names the issue of the saved item."""
    issue = data['item'].issue.full_name()

    assert _post(client, 'save_reading_order_item', {'sequence_number': 2},
                 item_id=data['reading_item'].id,
                 reading_order_id=data['reading_order'].id) == [
      'Eintrag %s gespeichert.' % issue]


def test_item_removed_from_reading_list(client, data):
    """The message names the issue and the reading list it left."""
    issue = data['item'].issue.full_name()

    assert _post(client, 'delete_reading_order_item',
                 item_id=data['reading_item'].id,
                 reading_order_id=data['reading_order'].id) == [
      'Eintrag <b>%s</b> aus der Leseliste Some Reading List entfernt'
      % issue]
