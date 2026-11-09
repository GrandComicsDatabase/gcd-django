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
