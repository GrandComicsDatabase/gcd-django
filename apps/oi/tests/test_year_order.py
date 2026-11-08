import pytest

from django import forms

from apps.oi.forms.publisher import (
    BrandGroupRevisionForm, BrandRevisionForm, BrandUseRevisionForm,
    IndiciaPublisherRevisionForm, PublisherRevisionForm)
from apps.oi.forms.series import SeriesRevisionForm
from apps.oi.forms.support import _check_year_order

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
                    indicia_publisher_add_values, brand_group_add_values,
                    brand_add_values, any_added_brand_group1,
                    series_add_values):
    return {
      'publisher': (PublisherRevisionForm, publisher_add_values),
      'indicia publisher': (IndiciaPublisherRevisionForm,
                            indicia_publisher_add_values),
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
