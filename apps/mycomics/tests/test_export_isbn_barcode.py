import csv
from io import StringIO
from runpy import run_path

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import include, path, reverse

from apps.gcd.models import Issue
from apps.mycomics import urls as mycomics_urls
from apps.mycomics.models import Collection, CollectionItem

# apps.mycomics.urls has the export view only with MYCOMICS = True.
with override_settings(MYCOMICS=True):
    urlpatterns = run_path(mycomics_urls.__file__)['urlpatterns']
urlpatterns += [path('', include('urls'))]

EXISTING_COLUMNS = [
    'series', 'publisher', 'series year', 'issue', 'grade', 'acquisition date',
    'location', 'purchase location', 'was read', 'for sale', 'signed',
    'price paid', '', 'description', 'tags']


@pytest.fixture
def issue(client, db, settings):
    """An issue collected by the seeded owner in the first collection."""
    settings.ROOT_URLCONF = __name__
    call_command('seed_development_data', verbosity=0)
    issue = Issue.objects.first()
    CollectionItem.objects.create(issue=issue).collections.add(1)
    client.force_login(Collection.objects.get(pk=1).collector.user)
    return issue


def _export(client):
    """The header and rows of the CSV export of the first collection."""
    response = client.get(reverse('export_collection',
                                  kwargs={'collection_id': 1}))
    body = b''.join(response.streaming_content).decode('utf-8-sig')
    return list(csv.reader(StringIO(body)))


def test_new_columns_are_after_the_existing_ones(client, issue):
    """No existing column changes its place, the new ones come last."""
    assert _export(client)[0] == EXISTING_COLUMNS + ['isbn', 'barcode']


@pytest.mark.parametrize('isbn, barcode', [
    ('9781401225773', '76194123456789'),
    ('9781401225773; 1401225772', ''),
    ('', '76194123456789'),
])
def test_row_has_the_isbn_and_barcode(client, issue, isbn, barcode):
    """The two columns hold the values of the issue, or stay empty."""
    Issue.objects.filter(id=issue.id).update(isbn=isbn, barcode=barcode)
    assert _export(client)[1][-2:] == [isbn, barcode]
