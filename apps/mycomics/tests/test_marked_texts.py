"""
The texts of the My Comics pages, and of the My Comics boxes on the issue
and series pages, are marked for translation: with a translation in the
message file, a page asked with ?lang=de shows them in German.
"""
import importlib
from datetime import datetime

import polib
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, override_settings
from django.urls import clear_url_caches, reverse

from apps.gcd.models import Issue, Publisher, Series
from apps.indexer.models import Indexer
from apps.mycomics import urls as mycomics_urls
from apps.mycomics.models import Collection, CollectionItem, Collector, \
                                 ConditionGradeScale, ReadingOrder, \
                                 ReadingOrderItem, Subscription
from apps.stddata.models import Country, Language

# Some of the newly marked texts as their msgids, with test translations.
GERMAN = {
    # templates/mycomics
    'Toggle navigation': 'Navigation umschalten',
    'Search...': 'Suche...',
    'Backed by the largest comic database on the planet, my.comics.org '
    'allows you to track your comic collection.':
        'Gestuetzt auf die groesste Comicdatenbank verwaltet my.comics.org '
        'deine Sammlung.',
    'non-public collection': 'nicht oeffentliche Sammlung',
    'Issue added %(date)s': 'Heft hinzugefuegt %(date)s',
    'Move %(issue)s To Another Collection':
        'Verschiebe %(issue)s in eine andere Sammlung',
    'In:': 'Enthalten in:',
    'I own this comic.': 'Ich besitze dieses Heft.',
    'Sequence Number': 'Laufende Nummer',
    'Issue / Story': 'Heft / Geschichte',
    'Reading List:': 'Leseliste:',
    'provided by <a href="%(url)s">%(name)s</a>':
        'bereitgestellt von <a href="%(url)s">%(name)s</a>',
    'Help': 'Hilfe',
    'Reading Lists': 'Leselisten',
    'is in digital form': 'ist digital',
    'Ongoing series can be <a href="%(url)s">subscribed</a> to a '
    'collection. You can pull issues added to the database since the last '
    'time you did such a pull.':
        'Laufende Serien koennen <a href="%(url)s">abonniert</a> werden.',
    'Owned': 'Im Besitz',
    'Change': 'Aendern',
    'Add This Issue To Collection': 'Heft in eine Sammlung',
    'Issue at www.comics.org': 'Heft auf www.comics.org',
    'Select Issues From This Series': 'Hefte dieser Serie waehlen',
    'without variants': 'ohne Varianten',
    'to add.': 'zum Hinzufuegen.',
    '(without variants) to': '(ohne Varianten) nach',
    'Series at www.comics.org': 'Serie auf www.comics.org',
    # apps/mycomics
    'Publication Date': 'Erscheinungsdatum',
    'I own': 'Ich besitze',
    'ownership': 'Besitz',
    'show condition': 'Zustand zeigen',
    'comic is for sale': 'Heft wird verkauft',
    'To use "Default for sale status" the "Show for sale status" needs to '
    'be activated.': 'Erst den Verkaufsstatus zeigen lassen.',
    'This comic is on my want list.': 'Dieses Heft steht auf meiner Liste.',
    'Editing Collection': 'Sammlung bearbeiten',
    'Editing Reading List: %(name)s': 'Leseliste bearbeiten: %(name)s',
    "Issue <a href='%(link)s'>%(issue)s</a> was added to your "
    "<b>%(collection)s</b> collection.":
        "Heft <a href='%(link)s'>%(issue)s</a> ist jetzt in der Sammlung "
        "<b>%(collection)s</b>.",
    'Only the owner of a collection can unsubscribe series.':
        'Nur der Besitzer der Sammlung kann Serien abbestellen.',
    'found that can be selected for import.': 'zum Import gefunden.',
}
# Singular and plural msgids, then the singular and plural translations.
GERMAN_PLURAL = [
    ('I own %(count)d copy of this comic.',
     'I own %(count)d copies of this comic.',
     'Ich besitze %(count)d Exemplar dieses Hefts.',
     'Ich besitze %(count)d Exemplare dieses Hefts.'),
    ('Recorded as for sale by %(counter)s user.',
     'Recorded as for sale by %(counter)s users.',
     'Bei %(counter)s Benutzer zu verkaufen.',
     'Bei %(counter)s Benutzern zu verkaufen.'),
    ('Tracked in %(total)s collection.',
     'Tracked in %(total)s collections.',
     'In %(total)s Sammlung erfasst.',
     'In %(total)s Sammlungen erfasst.'),
]

# The three texts with a number of the My Comics box of the issue page, as
# singular and plural msgids, and their test translations in six languages:
# the Plural-Forms of the language, then the forms of each text in the
# order of its plural rule.
BOX_PLURALS = [
    ('Tracked in %(total)s collection.', 'Tracked in %(total)s collections.'),
    ('I own %(count)d copy of this comic.',
     'I own %(count)d copies of this comic.'),
    ('Recorded as for sale by %(counter)s user.',
     'Recorded as for sale by %(counter)s users.'),
]
SIX_LANGUAGES = {
    'it': ('nplurals=2; plural=(n != 1);', [
      ('Registrato in %(total)s collezione.',
       'Registrato in %(total)s collezioni.'),
      ('Possiedo %(count)d copia di questo fumetto.',
       'Possiedo %(count)d copie di questo fumetto.'),
      ('In vendita presso %(counter)s utente.',
       'In vendita presso %(counter)s utenti.')]),
    'de': ('nplurals=2; plural=(n != 1);', [
      ('In %(total)s Sammlung erfasst.', 'In %(total)s Sammlungen erfasst.'),
      ('Ich besitze %(count)d Exemplar dieses Hefts.',
       'Ich besitze %(count)d Exemplare dieses Hefts.'),
      ('Bei %(counter)s Benutzer zu verkaufen.',
       'Bei %(counter)s Benutzern zu verkaufen.')]),
    'fr': ('nplurals=2; plural=(n > 1);', [
      ('Suivi dans %(total)s collection.',
       'Suivi dans %(total)s collections.'),
      ('Je possede %(count)d exemplaire de ce comic.',
       'Je possede %(count)d exemplaires de ce comic.'),
      ('En vente chez %(counter)s utilisateur.',
       'En vente chez %(counter)s utilisateurs.')]),
    'es': ('nplurals=2; plural=(n != 1);', [
      ('Seguido en %(total)s coleccion.', 'Seguido en %(total)s colecciones.'),
      ('Tengo %(count)d ejemplar de este comic.',
       'Tengo %(count)d ejemplares de este comic.'),
      ('En venta por %(counter)s usuario.',
       'En venta por %(counter)s usuarios.')]),
    'sr': ('nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && '
           'n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);', [
      ('Praceno: %(total)s zbirka.', 'Praceno: %(total)s zbirke.',
       'Praceno: %(total)s zbirki.'),
      ('Imam %(count)d primerak ovog stripa.',
       'Imam %(count)d primerka ovog stripa.',
       'Imam %(count)d primeraka ovog stripa.'),
      ('Na prodaju: %(counter)s prodavac.',
       'Na prodaju: %(counter)s prodavca.',
       'Na prodaju: %(counter)s prodavaca.')]),
    'ja': ('nplurals=1; plural=0;', [
      ('%(total)s korekushon de kanri.',),
      ('Kono komikku o %(count)d-satsu motte imasu.',),
      ('%(counter)s-nin ga urimasu.',)]),
}
# The numbers shown, and the form that each language takes for each of
# them: French takes the singular for 0 and 1, Serbian has three forms (1
# and 21 / 2 to 4 / 0, 5 to 20), Japanese has one.
COUNTS = (0, 1, 2, 5, 21)
FORMS = {'it': (1, 0, 1, 1, 1), 'de': (1, 0, 1, 1, 1),
         'fr': (0, 0, 1, 1, 1), 'es': (1, 0, 1, 1, 1),
         'sr': (2, 0, 1, 2, 0), 'ja': (0, 0, 0, 0, 0)}


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
    catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8',
                        'Plural-Forms': 'nplurals=2; plural=(n != 1);'}
    for msgid, msgstr in GERMAN.items():
        catalog.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    for msgid, plural, one, other in GERMAN_PLURAL:
        catalog.append(polib.POEntry(msgid=msgid, msgid_plural=plural,
                                     msgstr_plural={0: one, 1: other}))
    folder = tmp_path / 'de' / 'LC_MESSAGES'
    folder.mkdir(parents=True)
    catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path)]


def _collector(name, country, language):
    """A user with an indexer profile and a collector with two collections."""
    user = User.objects.create_user(name)
    Indexer.objects.create(user=user, country=country)
    Collector.objects.create_collector(
      user, default_language=language,
      grade_system=ConditionGradeScale.objects.create(name='Some Scale'))
    return user


@pytest.fixture
def data(db, client, german):
    """
    The logged-in collector has an issue in the default have collection,
    which shows the own/want status, a second collection, a subscription
    and a reading list; another collector has a public reading list. All on
    My Comics.
    """
    country = Country.objects.get_or_create(
      id=942, defaults={'code': 'n8', 'name': 'Testland M'})[0]
    language = Language.objects.get_or_create(
      id=942, defaults={'code': 'n8', 'name': 'Testish M'})[0]
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, is_comics_publication=True,
      is_current=True, publication_dates='1990',
      publisher=Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1990))
    issue = Issue.objects.create(number='1', series=series, sort_code=1,
                                 publication_date='1990',
                                 key_date='1990-01-00')
    user = _collector('some.collector', country, language)
    have = user.collector.default_have_collection
    Collection.objects.filter(id=have.id).update(own_used=True)
    item = CollectionItem.objects.create(issue=issue, own=True,
                                         for_sale=True)
    item.collections.add(have)
    Subscription.objects.create(series=series, collection=have,
                                last_pulled=datetime(2026, 1, 2))
    reading_order = ReadingOrder.objects.create(
      collector=user.collector, name='Some Reading List')
    other_user = _collector('other.collector', country, language)
    shared = ReadingOrder.objects.create(collector=other_user.collector,
                                         name='Shared Reading List',
                                         public=True)
    client.force_login(user)
    with override_settings(MYCOMICS=True):
        _reload_urls()
        yield {'series': series, 'issue': issue, 'item': item, 'have': have,
               'other': Collection.objects.create(collector=user.collector,
                                                  name='Some Collection'),
               'reading_order': reading_order, 'shared': shared,
               'reading_item': ReadingOrderItem.objects.create(
                 issue=issue, reading_order=reading_order,
                 sequence_number=1),
               'foreign_subscription': Subscription.objects.create(
                 series=series,
                 collection=other_user.collector.default_have_collection,
                 last_pulled=datetime(2026, 1, 2))}
    _reload_urls()


def _have(data):
    """The keyword arguments of the default have collection."""
    return {'collection_id': data['have'].id}


# Page name, its keyword arguments, query, the German and the English texts.
PAGES = {
  'collection list': (
    'collections_list', lambda d: {}, '',
    ['>Navigation umschalten<', 'placeholder="Suche..."',
     'title="nicht oeffentliche Sammlung"'],
    ['>Toggle navigation<', 'placeholder="Search..."',
     'title="non-public collection"']),
  'reading lists': (
    'reading_orders_list', lambda d: {}, '',
    ['title="nicht oeffentliche Sammlung"'],
    ['title="non-public collection"']),
  'collection': (
    'view_collection', _have, '',
    ['title="nicht oeffentliche Sammlung"', 'Erscheinungsdatum',
     '>Ich besitze</option>'],
    ['title="non-public collection"', 'Publication Date',
     '>I own</option>']),
  'collection series': (
    'view_collection_series', _have, '',
    ['title="nicht oeffentliche Sammlung"'],
    ['title="non-public collection"']),
  'subscriptions': (
    'subscriptions_collection', _have, '',
    ['>Heft hinzugefuegt 2026-01-02</div>'],
    ['>Issue added 2026-01-02</div>']),
  'item': (
    'view_item',
    lambda d: {'item_id': d['item'].id, 'collection_id': d['have'].id}, '',
    ['in eine andere Sammlung </h4>', '<h4>Enthalten in: <a',
     'Ich besitze dieses Heft.<br>', '>Besitz</label>'],
    ['To Another Collection </h4>', '<h4>In: <a', 'I own this comic.<br>',
     '>Ownership</label>']),
  'reading list item': (
    'view_reading_order_item',
    lambda d: {'item_id': d['reading_item'].id,
               'reading_order_id': d['reading_order'].id}, '',
    ['<h4>Enthalten in: <a'], ['<h4>In: <a']),
  'edit reading list': (
    'edit_reading_order',
    lambda d: {'reading_order_id': d['reading_order'].id}, '',
    ['Leseliste bearbeiten: Some Reading List', '> Laufende Nummer </th>',
     '> Heft / Geschichte </th>'],
    ['Editing Reading List: Some Reading List', '> Sequence Number </th>',
     '> Issue / Story </th>']),
  'shared reading list': (
    'view_reading_order',
    lambda d: {'reading_order_id': d['shared'].id}, '',
    ['Leseliste: Shared Reading List', 'bereitgestellt von <a href=',
     '>Leselisten</a>'],
    ['Reading List: Shared Reading List', 'provided by <a href=',
     '>Reading Lists</a>']),
  'help': (
    'mycomics_help', lambda d: {}, '',
    ['<li>ist digital</li>', 'Laufende Serien koennen <a href="%s">'
     'abonniert</a> werden.</li>', '>Hilfe</a>'],
    ['<li>is in digital form</li>', 'Ongoing series can be <a href="%s">'
     'subscribed</a> to a collection.', '>Help</a>']),
  'issue': (
    'show_issue', lambda d: {'issue_id': d['issue'].id}, '',
    ['In 1 Sammlung erfasst.', 'Ich besitze 1 Exemplar dieses Hefts.',
     '<br>Bei 1 Benutzer zu verkaufen.', '>Aendern</button>',
     'value="Heft in eine Sammlung"', '>Heft auf www.comics.org</a>'],
    ['Tracked in 1 collection.', 'I own 1 copy of this comic.',
     '<br>Recorded as for sale by 1 user.', '>Change</button>',
     'value="Add This Issue To Collection"',
     '>Issue at www.comics.org</a>']),
  'series': (
    'show_series', lambda d: {'series_id': d['series'].id}, '',
    ['value="Hefte dieser Serie waehlen"', '>ohne Varianten</option>',
     'zum Hinzufuegen.', '>(ohne Varianten) nach</span>',
     '>Serie auf www.comics.org</a>', '> Im Besitz </td>'],
    ['value="Select Issues From This Series"',
     '>without variants</option>', 'to add.',
     '>(without variants) to</span>', '>Series at www.comics.org</a>',
     '> Owned </td>']),
  'edit collection': (
    'edit_collection', _have, '',
    ['Sammlung bearbeiten', 'Zustand zeigen', 'Heft wird verkauft'],
    ['Editing Collection', 'Show condition', 'comic is for sale']),
  'series issues to select': (
    'my_series_issues', lambda d: {'series_id': d['series'].id},
    '&which_issues=base_issues',
    ['zum Import gefunden.'], ['found that can be selected for import.']),
  'foreign subscription': (
    'unsubscribe',
    lambda d: {'subscription_id': d['foreign_subscription'].id}, '',
    ['Nur der Besitzer der Sammlung kann Serien abbestellen.'],
    ['Only the owner of a collection can unsubscribe series.']),
}


@pytest.mark.parametrize('lang', ['de', 'en'])
@pytest.mark.parametrize('page', PAGES)
def test_page_shows_the_marked_texts(client, data, page, lang):
    """The page shows the texts in German with ?lang=de, else in English."""
    name, kwargs, query, german, english = PAGES[page]
    response = client.get(reverse(name, kwargs=kwargs(data)) + '?lang=' +
                          lang + query)
    content = response.content.decode()
    subscribe = reverse('subscriptions_collection', kwargs=_have(data))

    assert response.status_code == 200
    for text in german if lang == 'de' else english:
        assert (text % subscribe if '%s' in text else text) in content


def test_login_page_shows_the_marked_texts(data):
    """The login page of My Comics shows its introduction in German."""
    content = Client().get(reverse('my_login') + '?lang=de').content.decode()

    assert 'Gestuetzt auf die groesste Comicdatenbank verwaltet ' \
           'my.comics.org deine Sammlung.' in content


def test_issue_page_shows_the_want_list_in_german(client, data):
    """The My Comics box of the issue page names the want list."""
    CollectionItem.objects.filter(id=data['item'].id).update(own=False)

    content = client.get(reverse('show_issue',
                                 kwargs={'issue_id': data['issue'].id}) +
                         '?lang=de').content.decode()

    assert 'Dieses Heft steht auf meiner Liste.' in content


def test_collection_settings_error_in_german(client, data):
    """A default for sale status without the for sale status is refused."""
    response = client.post(reverse('edit_collection', kwargs=_have(data)) +
                           '?lang=de', {'name': 'Default have collection',
                                        'for_sale_default': 'True'})

    assert response.status_code == 200
    assert 'Erst den Verkaufsstatus zeigen lassen.' in \
           response.content.decode()


def test_issue_added_message_in_german(client, data):
    """The message names the issue and the collection it went into."""
    response = client.post(reverse('my_issue',
                                   kwargs={'issue_id': data['issue'].id}) +
                           '?lang=de', {'collection_id': data['other'].id})
    shown = [str(message) for message in get_messages(response.wsgi_request)]

    assert response.status_code == 302
    assert shown[-1].endswith(' ist jetzt in der Sammlung '
                              '<b>Some Collection</b>.')


@pytest.fixture
def six_languages(settings, tmp_path, german):
    """
    Message files of six languages, each with its plural rule, hold the test
    translations of the three texts with a number of the issue page box.
    """
    for lang, (plural_forms, texts) in SIX_LANGUAGES.items():
        catalog = polib.POFile()
        catalog.metadata = {'Content-Type': 'text/plain; charset=UTF-8',
                            'Plural-Forms': plural_forms}
        for (msgid, plural), forms in zip(BOX_PLURALS, texts):
            catalog.append(polib.POEntry(msgid=msgid, msgid_plural=plural,
                                         msgstr_plural=dict(enumerate(forms))))
        folder = tmp_path / 'six' / lang / 'LC_MESSAGES'
        folder.mkdir(parents=True)
        catalog.save_as_mofile(str(folder / 'django.mo'))
    settings.LOCALE_PATHS = [str(tmp_path / 'six')]
    settings.LANGUAGES = list(settings.LANGUAGES) + [
      ('fr', 'French'), ('es', 'Spanish'), ('sr', 'Serbian'),
      ('ja', 'Japanese')]


@pytest.mark.parametrize('lang', SIX_LANGUAGES)
def test_issue_page_box_numbers_in_six_languages(client, data, six_languages,
                                                 lang):
    """
    For 0, 1, 2, 5 and 21 items, the box shows each text with a number in
    the form that the plural rule of the language takes for that number.
    """
    issue = data['issue']
    url = reverse('show_issue', kwargs={'issue_id': issue.id})
    texts = SIX_LANGUAGES[lang][1]
    for count, form in zip(COUNTS, FORMS[lang]):
        CollectionItem.objects.filter(issue=issue).delete()
        for number in range(count):
            item = CollectionItem.objects.create(issue=issue, own=True,
                                                 for_sale=True)
            item.collections.add(data['have'])
        content = client.get(url + '?lang=' + lang).content.decode()
        expected = [texts[0][form] % {'total': count}]
        if count:
            # without items the box shows neither the copies nor the users
            expected += [texts[1][form] % {'count': count},
                         texts[2][form] % {'counter': count}]

        for text in expected:
            assert text in content, (lang, count, text)
