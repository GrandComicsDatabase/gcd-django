import re

import pytest

from django.urls import reverse

from apps.oi import states
from apps.oi.models import Changeset, CTYPES, IssueRevision
from apps.oi.templatetags.compare import field_value
from apps.stddata.models import Currency


def _price_value(price, changed=True):
    revision = IssueRevision(price=price)
    revision.changed = {'price': changed}
    return field_value(revision, 'price')


@pytest.mark.django_db
@pytest.mark.parametrize('price', [
    '',
    '0.50 USD',
    '2.99 USD; 3.99 USD (newsstand)',
    '3,99 EUR DE; 3,50 EUR AT; 1,50 EUR FR',
    '2/6 [0-2-6 GBP]',
    '0.00 FREE',
    '[none]',
])
def test_no_note_for_known_currency_codes(price):
    assert _price_value(price) == price


@pytest.mark.django_db
@pytest.mark.parametrize('price, unknown', [
    ('2.99 UDS', '"2.99 UDS"'),
    ('2.99 usd', '"2.99 usd"'),
    ('2.99', '"2.99"'),
    ('$2.99', '"$2.99"'),
    ('2.99 USD; 3.99 CDA (newsstand); 1.50', '"3.99 CDA", "1.50"'),
])
def test_note_for_unknown_or_missing_currency_code(price, unknown):
    assert _price_value(price) == \
        '%s (note: no known currency code in %s)' % (price, unknown)


def test_no_note_for_a_price_that_did_not_change():
    assert _price_value('2.99 UDS', changed=False) == '2.99 UDS'
    # the previous revision in the compare page
    assert field_value(IssueRevision(price='2.99 UDS'), 'price') == \
        '2.99 UDS'


@pytest.mark.django_db
def test_currency_list_is_the_currency_table():
    assert 'note' in _price_value('2.50 DEM')
    Currency.objects.create(code='DEM', name='Deutsche Mark')
    assert _price_value('2.50 DEM') == '2.50 DEM'


@pytest.mark.django_db
def test_compare_page_notes_unknown_currency_code(client, any_indexer,
                                                  any_added_issue):
    # the price of the issue is 0.10 USD
    changeset = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=changeset)
    revision.price = '0.10 UDS'
    revision.save()
    client.force_login(any_indexer)

    response = client.get(reverse('compare', kwargs={'id': changeset.id}))

    assert response.status_code == 200
    # the changed price is shown as a diff, split by tags
    text = re.sub('<[^>]*>', '', response.content.decode())
    assert ('0.10 UDS (note: no known currency code in &quot;0.10 UDS&quot;)'
            in text)
    assert text.count('no known currency code') == 1
