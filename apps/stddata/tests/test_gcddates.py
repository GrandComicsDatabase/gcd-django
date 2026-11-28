"""Tests for the dates written as GCD writes them (apps.stddata.gcddates)."""

from datetime import date

import pytest

from apps.oi.models import IssueRevision
from apps.stddata import gcddates

ENGLISH = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December']
ITALIAN = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
           'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre',
           'Dicembre']
FORMS = ['{day} {month} {year}', '{month} {day}, {year}',
         '[{month} {year}]', '{year}']
DAY_1945 = date(1945, 1, 7)


def test_month_and_year():
    """C1: {month} {year} writes the month name and the year."""
    texts = [gcddates.publication_date(date(1990, month, 1),
                                       '{month} {year}', ENGLISH)
             for month in range(1, 13)]

    assert texts[0] == 'January 1990'
    assert texts == [name + ' 1990' for name in ENGLISH]


def test_key_dates_of_a_monthly():
    """C2: with MONTH precision the key date ends in 00."""
    keys = [gcddates.key_date(date(1990, month, 1), gcddates.MONTH)
            for month in range(1, 13)]

    assert keys[0] == '1990-01-00'
    assert keys == ['1990-%02d-00' % month for month in range(1, 13)]


def test_key_date_precisions():
    """C3: DAY keeps the day, MONTH and YEAR write 00 for what they drop."""
    day = date(1990, 1, 3)

    assert gcddates.key_date(day) == '1990-01-03'
    assert gcddates.key_date(day, gcddates.DAY) == '1990-01-03'
    assert gcddates.key_date(day, gcddates.MONTH) == '1990-01-00'
    assert gcddates.key_date(day, gcddates.YEAR) == '1990-00-00'


@pytest.mark.parametrize('pattern, names, text', [
    ('{day} {month} {year}', ITALIAN, '7 Gennaio 1945'),
    ('{month} {day}, {year}', ENGLISH, 'January 7, 1945'),
    ('[{month} {year}]', ENGLISH, '[January 1945]'),
    ('{year}', ENGLISH, '1945'),
])
def test_written_forms(pattern, names, text):
    """C4: each form gives the text as printed, the day without a 0."""
    assert gcddates.publication_date(DAY_1945, pattern, names) == text


@pytest.mark.parametrize('pattern, names, text', [
    ('{year.real}', ENGLISH, '{year.real}'),
    ('{year} {', ENGLISH, '1945 {'),
    ('{{year}}', ENGLISH, '{1945}'),
    ('{month} {year}', ['{year}{day}'] + ENGLISH[1:], '{year}{day} 1945'),
])
def test_typed_braces_are_kept(pattern, names, text):
    """C4: only the three placeholders are replaced; typed text is kept."""
    assert gcddates.publication_date(DAY_1945, pattern, names) == text


def test_precision_of_the_written_forms():
    """C5: {day} gives DAY, else {month} gives MONTH, else YEAR."""
    precisions = [gcddates.pattern_precision(form) for form in FORMS]

    assert precisions == [gcddates.DAY, gcddates.DAY, gcddates.MONTH,
                          gcddates.YEAR]


def test_usable_written_forms():
    """C6: the forms of C4 can be used."""
    assert [gcddates.pattern_error(form) for form in FORMS] == [''] * 4


@pytest.mark.parametrize('pattern', [
    '', '{month}', '{day} {year}', '{week} {year}', '{year.real}',
    '{year} {', '{year} }',
])
def test_unusable_written_forms(pattern):
    """C6: no {year}, {day} without {month} or a stray brace: a reason."""
    reason = gcddates.pattern_error(pattern)

    assert isinstance(reason, str)
    assert reason


@pytest.mark.parametrize('pattern', [
    '{ye{month}ar}{year}', '{month} {year} {mon{day}th}',
])
def test_a_placeholder_made_of_two_pieces_is_refused(pattern):
    """C6: braces left around a placeholder would be printed: a reason."""
    assert '{' in gcddates.publication_date(DAY_1945, pattern, ENGLISH)
    assert gcddates.pattern_error(pattern)


def test_every_key_date_from_1700_to_2099_is_valid():
    """C7: every day of 1700-2099 gives key dates that the model accepts."""
    validators = IssueRevision._meta.get_field('key_date').validators
    first = date(1700, 1, 1).toordinal()
    last = date(2099, 12, 31).toordinal()
    for ordinal in range(first, last + 1):
        day = date.fromordinal(ordinal)
        by_day = gcddates.key_date(day, gcddates.DAY)
        by_month = gcddates.key_date(day, gcddates.MONTH)
        by_year = gcddates.key_date(day, gcddates.YEAR)
        for text in (by_day, by_month, by_year):
            for validator in validators:
                validator(text)
        assert date.fromisoformat(by_day) == day
        assert by_month == by_day[:7] + '-00'
        assert by_year == by_day[:4] + '-00-00'


@pytest.mark.parametrize('day', [date(1699, 12, 31), date(2100, 1, 1)])
def test_key_date_outside_the_years_of_gcd(day):
    """C8: a key date before 1700 or after 2099 raises ValueError."""
    with pytest.raises(ValueError):
        gcddates.key_date(day)


def test_key_date_of_an_unknown_precision():
    """C8: a precision other than YEAR, MONTH and DAY raises ValueError."""
    with pytest.raises(ValueError):
        gcddates.key_date(date(1990, 1, 3), 'week')
