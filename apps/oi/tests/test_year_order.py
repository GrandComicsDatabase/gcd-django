from datetime import date

import pytest

from django import forms
from django.urls import reverse

from apps.gcd.models import Publisher
from apps.oi import states
from apps.oi.forms import ExternalLinkRevisionFormSet
from apps.oi.forms.publisher import (
    BrandGroupRevisionForm, BrandRevisionForm, BrandUseRevisionForm,
    IndiciaPrinterRevisionForm, IndiciaPublisherRevisionForm,
    PrinterRevisionForm, PublisherRevisionForm)
from apps.oi.forms.series import SeriesRevisionForm
from apps.oi.forms.support import _check_year_order
from apps.oi.models import Changeset, CTYPES, PublisherRevision

PUBLISHER_DATA = {'name': 'Name', 'notes': '', 'comments': '',
                  'year_overall_began': None, 'year_overall_ended': None}
SERIES_DATA = {'name': 'Name', 'leading_article': False, 'color': '',
               'dimensions': '', 'paper_stock': '', 'binding': '',
               'publishing_format': '', 'comments': ''}


@pytest.mark.parametrize('years', (
    {},
    {'year_began': 1990},
    {'year_ended': 1990},
    {'year_began': 1990, 'year_ended': 1990},
    {'year_began': 1990, 'year_ended': 1991},
    {'year_overall_began': 1990, 'year_overall_ended': 1991},
))
def test_years_in_order_pass(years):
    _check_year_order(years)


@pytest.mark.parametrize(('years', 'message'), (
    ({'year_began': 1991, 'year_ended': 1990},
     'Year ended cannot be before year began.'),
    ({'year_overall_began': 1991, 'year_overall_ended': 1990},
     'Year overall ended cannot be before year overall began.'),
))
def test_year_ended_before_year_began_fails(years, message):
    with pytest.raises(forms.ValidationError, match=message):
        _check_year_order(years)


def _form_data(values, **changes):
    """
    The values of a revision as the POST data of its form.
    """
    data = {}
    for key, value in dict(values, **changes).items():
        if value is None or value is False:
            continue
        if value is True:
            data[key] = 'on'
        elif hasattr(value, 'pk'):
            data[key] = value.pk
        else:
            data[key] = value
    return data


@pytest.fixture
def form_and_values(request, publisher_add_values,
                    indicia_publisher_add_values, printer_add_values,
                    indicia_printer_add_values, brand_group_add_values,
                    brand_add_values, any_added_brand_group1,
                    series_add_values):
    return {
      'publisher': (PublisherRevisionForm, publisher_add_values),
      'indicia publisher': (IndiciaPublisherRevisionForm,
                            indicia_publisher_add_values),
      'printer': (PrinterRevisionForm, printer_add_values),
      'indicia printer': (IndiciaPrinterRevisionForm,
                          indicia_printer_add_values),
      'brand group': (BrandGroupRevisionForm, brand_group_add_values),
      'brand': (BrandRevisionForm,
                dict(brand_add_values, group=[any_added_brand_group1.pk])),
      'brand use': (BrandUseRevisionForm, {'notes': ''}),
      'series': (SeriesRevisionForm, dict(series_add_values,
                                          is_current=False)),
    }[request.param]


@pytest.mark.django_db
@pytest.mark.parametrize('form_and_values', (
    'publisher', 'indicia publisher', 'brand group', 'brand', 'brand use',
    'series'), indirect=True)
def test_edit_forms_refuse_a_year_ended_before_the_year_began(
        form_and_values):
    form_class, values = form_and_values

    in_order = form_class(_form_data(values, year_began=1989,
                                     year_ended=1990))
    assert in_order.is_valid(), in_order.errors

    reversed_years = form_class(_form_data(values, year_began=1990,
                                           year_ended=1989))
    assert not reversed_years.is_valid()
    assert reversed_years.errors == {
      '__all__': ['Year ended cannot be before year began.']}


@pytest.mark.django_db
@pytest.mark.parametrize('form_and_values', ('publisher', 'brand group'),
                         indirect=True)
def test_edit_forms_refuse_overall_years_in_reverse(form_and_values):
    form_class, values = form_and_values

    in_order = form_class(_form_data(values, year_began=1995,
                                     year_overall_began=1989,
                                     year_overall_ended=1990))
    assert in_order.is_valid(), in_order.errors

    reversed_years = form_class(_form_data(values, year_began=1995,
                                           year_overall_began=1990,
                                           year_overall_ended=1989))
    assert not reversed_years.is_valid()
    assert reversed_years.errors == {
      '__all__': ['Year overall ended cannot be before year overall '
                  'began.']}


YEAR_FORMS = ('publisher', 'indicia publisher', 'printer', 'indicia printer',
              'brand group', 'brand', 'brand use', 'series')


def _range_error(label):
    return '%s must be between 1700 and %d.' % (label, date.today().year + 1)


@pytest.mark.django_db
@pytest.mark.parametrize('form_and_values', YEAR_FORMS, indirect=True)
def test_edit_forms_refuse_a_year_out_of_range(form_and_values):
    form_class, values = form_and_values

    for year in (0, 1699, date.today().year + 2):
        for field, label in (('year_began', 'Year began'),
                             ('year_ended', 'Year ended')):
            years = {'year_began': 1990, 'year_ended': None, field: year}
            form = form_class(_form_data(values, **years))
            assert not form.is_valid(), (field, year)
            assert form.errors == {'__all__': [_range_error(label)]}


@pytest.mark.django_db
@pytest.mark.parametrize('form_and_values', YEAR_FORMS, indirect=True)
def test_edit_forms_accept_the_limits_of_the_range(form_and_values):
    form_class, values = form_and_values

    form = form_class(_form_data(values, year_began=1700,
                                 year_ended=date.today().year + 1))
    assert form.is_valid(), form.errors


@pytest.mark.django_db
@pytest.mark.parametrize('form_and_values', YEAR_FORMS, indirect=True)
def test_only_a_changed_year_has_to_be_in_range(form_and_values):
    form_class, values = form_and_values
    stored = {'year_began': 1500, 'year_ended': 3000}

    def form_for(**years):
        return form_class(_form_data(values, **years),
                          instance=form_class._meta.model(**stored))

    unrelated_edit = form_for(**stored)
    assert unrelated_edit.is_valid(), unrelated_edit.errors

    one_corrected = form_for(year_began=1960, year_ended=3000)
    assert one_corrected.is_valid(), one_corrected.errors

    began_changed = form_for(year_began=1501, year_ended=3000)
    assert not began_changed.is_valid()
    assert began_changed.errors == {'__all__': [_range_error('Year began')]}

    ended_changed = form_for(year_began=1500, year_ended=3001)
    assert not ended_changed.is_valid()
    assert ended_changed.errors == {'__all__': [_range_error('Year ended')]}


def _login_editor(client, user):
    user.is_superuser = True
    user.save()
    user.indexer.max_reservations = 10
    user.indexer.save()
    client.force_login(user)


@pytest.mark.django_db
def test_edit_view_of_a_publisher_with_an_old_year(client, any_indexer,
                                                   any_added_publisher,
                                                   publisher_add_values):
    publisher = any_added_publisher
    Publisher.objects.filter(id=publisher.id).update(year_began=1500)
    _login_editor(client, any_indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'publisher',
                                'id': publisher.id}))
    revision = PublisherRevision.objects.get(
      publisher=publisher, changeset__state=states.OPEN)
    assert revision.year_began == 1500
    url = reverse('process_revision', kwargs={'model_name': 'publisher',
                                              'id': revision.id})
    prefix = ExternalLinkRevisionFormSet.get_default_prefix()
    post = {'save': 'Save', prefix + '-TOTAL_FORMS': 0,
            prefix + '-INITIAL_FORMS': 0}

    response = client.post(url, dict(post, **_form_data(
      publisher_add_values, year_began=1501, notes='Changed')))
    assert response.status_code == 200
    assert _range_error('Year began') in response.content.decode()
    revision.refresh_from_db()
    assert revision.year_began == 1500
    assert revision.notes != 'Changed'

    response = client.post(url, dict(post, **_form_data(
      publisher_add_values, year_began=1500, notes='Changed')))
    assert response.status_code == 302
    revision.refresh_from_db()
    assert revision.year_began == 1500
    assert revision.notes == 'Changed'


@pytest.mark.django_db
def test_add_brand_use_shows_the_year_error(client, any_indexer,
                                            any_added_brand,
                                            any_added_publisher):
    _login_editor(client, any_indexer)

    response = client.post(
      reverse('add_brand_use', kwargs={'brand_id': any_added_brand.id,
                                       'publisher_id': any_added_publisher.id
                                       }),
      {'year_began': 1500, 'notes': '', 'comments': ''})

    assert response.status_code == 200
    assert _range_error('Year began') in response.content.decode()
    assert not Changeset.objects.filter(
      change_type=CTYPES['brand_use']).exists()
