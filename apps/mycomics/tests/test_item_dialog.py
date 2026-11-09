import re
from runpy import run_path

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import include, path, reverse

from apps.gcd.models import Issue
from apps.mycomics import urls as mycomics_urls
from apps.mycomics.models import Collection, CollectionItem

# apps.mycomics.urls has the views of the dialog only with MYCOMICS = True.
with override_settings(MYCOMICS=True):
    urlpatterns = run_path(mycomics_urls.__file__)['urlpatterns']
urlpatterns += [path('', include('urls'))]


@pytest.fixture
def dialog(client, db, settings):
    """The rendered dialog, for an item of a collection that uses all fields."""
    settings.ROOT_URLCONF = __name__
    call_command('seed_development_data', verbosity=0)
    Collection.objects.filter(pk=1).update(sell_date_used=True, own_used=True,
                                           rating_used=True)
    item = CollectionItem.objects.create(issue=Issue.objects.first())
    item.collections.add(1)
    client.force_login(Collection.objects.get(pk=1).collector.user)
    page = client.get(reverse('view_item', kwargs={
      'item_id': item.id, 'collection_id': 1})).content.decode()
    start = page.index('id="edit-item"')
    return page[start:page.index('<!-- /.modal -->', start)]


@pytest.mark.parametrize('field', [
    'keywords', 'own', 'for_sale', 'price_paid', 'price_paid_currency',
    'rating', 'acquisition_date-date', 'sell_date-date'])
def test_label_and_field_are_side_by_side(dialog, field):
    """The form is horizontal, each field has its label on its left."""
    assert re.search(r'<form [^>]*\s+class="form-horizontal">', dialog)
    assert re.search(r'<label class="col-xs-4 col-sm-3 control-label" '
                     r'for="id_%s">[^<]*</label>'
                     r'<div class="col-xs-8 col-sm-9">' % field, dialog)


@pytest.fixture
def item(client, db, settings):
    """An item of the seeded owner, in a collection with no date field."""
    settings.ROOT_URLCONF = __name__
    call_command('seed_development_data', verbosity=0)
    Collection.objects.filter(pk=1).update(acquisition_date_used=False)
    item = CollectionItem.objects.create(issue=Issue.objects.first())
    item.collections.add(1)
    client.force_login(Collection.objects.get(pk=1).collector.user)
    return item


def _page(client, item):
    """The page of the item, as rendered for the current user."""
    response = client.get(reverse('view_item', kwargs={
      'item_id': item.id, 'collection_id': 1}))
    assert response.status_code == 200
    return response.content.decode()


def _targets(page):
    """The ids of the date fields filled by the Today buttons of the page."""
    return re.findall(r'<button type="button" class="btn btn-default"\s+'
                      r"onclick=\"set_today\('([^']+)'\);\">\s*Today\s*"
                      r'</button>', page)


@pytest.mark.parametrize('dates, targets', [
    ({}, []),
    ({'acquisition_date_used': True}, ['id_acquisition_date-date']),
    ({'sell_date_used': True}, ['id_sell_date-date']),
    ({'acquisition_date_used': True, 'sell_date_used': True},
     ['id_acquisition_date-date', 'id_sell_date-date']),
])
def test_each_date_field_in_use_has_a_button(client, item, dates, targets):
    """The owner has the dialog, with a plain button per date field in use."""
    Collection.objects.filter(pk=1).update(**dates)
    page = _page(client, item)
    assert 'id="edit-item"' in page and 'function set_today(' in page
    assert _targets(page) == targets
    assert all('id="%s"' % target in page for target in targets)


def test_button_for_a_date_of_another_collection(client, item):
    """The date fields follow all the collections of the item."""
    item.collections.add(101)
    Collection.objects.filter(pk=101).update(sell_date_used=True)
    assert _targets(_page(client, item)) == ['id_sell_date-date']


def test_visitor_of_a_public_collection_has_no_button(client, item):
    """The dialog and the buttons are for the owner of the collection."""
    Collection.objects.filter(pk=1).update(public=True,
                                           acquisition_date_used=True)
    client.logout()
    page = _page(client, item)
    assert 'id="edit-item"' not in page and 'set_today(' not in page


def test_date_as_year_month_day_is_saved(client, item):
    """A date written as YYYY-MM-DD is accepted by the field."""
    Collection.objects.filter(pk=1).update(acquisition_date_used=True)
    page = _page(client, item)
    name = re.search(r'name="([^"]+)"[^>]*id="%s"' % _targets(page)[0], page)
    response = client.post(reverse('save_item', kwargs={
      'item_id': item.id, 'collection_id': 1}), {name.group(1): '2026-11-09'})
    item.refresh_from_db()
    assert response.status_code == 302
    assert str(item.acquisition_date) == '2026-11-09'
