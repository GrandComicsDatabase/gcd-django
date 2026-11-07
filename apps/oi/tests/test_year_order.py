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


@pytest.mark.django_db
@pytest.mark.parametrize(('form_class', 'data'), (
    (PublisherRevisionForm, PUBLISHER_DATA),
    (IndiciaPublisherRevisionForm, PUBLISHER_DATA),
    (BrandGroupRevisionForm, PUBLISHER_DATA),
    (BrandRevisionForm, PUBLISHER_DATA),
    (BrandUseRevisionForm, {'notes': '', 'comments': ''}),
    (SeriesRevisionForm, SERIES_DATA),
))
def test_edit_forms_check_the_year_order(form_class, data):
    form = form_class()
    form.cleaned_data = dict(data, year_began=1991, year_ended=1990)
    form._errors = {}

    with pytest.raises(forms.ValidationError,
                       match='Year ended cannot be before year began.'):
        form.clean()
