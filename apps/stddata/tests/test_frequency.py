"""Tests for the dates of a rule that repeats (apps.stddata.frequency)."""

from datetime import date
from itertools import islice, takewhile

import pytest

from apps.stddata import frequency


def _first(count, dates):
    """Return the first count dates of a generator as a list."""
    return list(islice(dates, count))


def _in_year(year, dates):
    """Return the dates of a generator up to the end of a year."""
    return list(takewhile(lambda day: day.year == year, dates))


def test_months_from_the_first_of_january():
    """E1: a monthly from January 1 comes out on the first of each month."""
    dates = _first(12, frequency.occurrences(date(1990, 1, 1),
                                             frequency.MONTHS))

    assert dates == [date(1990, month, 1) for month in range(1, 13)]


def test_months_take_the_last_day_of_a_short_month():
    """E2: a day past the end of a month gives the last day of that month."""
    dates = _first(4, frequency.occurrences(date(1990, 1, 31),
                                            frequency.MONTHS))
    leap = _first(2, frequency.occurrences(date(1992, 1, 31),
                                           frequency.MONTHS))

    assert dates == [date(1990, 1, 31), date(1990, 2, 28),
                     date(1990, 3, 31), date(1990, 4, 30)]
    assert leap[1] == date(1992, 2, 29)


def test_every_three_months():
    """E3: every 3 months keeps the day of the first date."""
    dates = _first(4, frequency.occurrences(date(1990, 1, 15),
                                            frequency.MONTHS, 3))

    assert dates == [date(1990, 1, 15), date(1990, 4, 15),
                     date(1990, 7, 15), date(1990, 10, 15)]


def test_weeks_on_the_weekday_of_the_first_date():
    """E4: with no weekday ticked a weekly keeps the first date's weekday."""
    dates = _first(53, frequency.occurrences(date(1990, 1, 3),
                                             frequency.WEEKS))

    assert [day.year for day in dates[:52]] == [1990] * 52
    assert dates[0] == date(1990, 1, 3)
    assert dates[51] == date(1990, 12, 26)
    assert dates[52] == date(1991, 1, 2)


def test_weeks_on_a_ticked_weekday():
    """E5: a ticked weekday wins over the weekday of the first date."""
    dates = frequency.occurrences(date(1990, 1, 1), frequency.WEEKS,
                                  weekdays=[2])

    assert next(dates) == date(1990, 1, 3)


@pytest.mark.parametrize('weekdays, count', [
    ([0, 1, 2, 3, 4, 5], 313),
    ([6], 52),
    ([0, 1, 2, 3, 4, 5, 6], 365),
])
def test_weeks_take_every_ticked_day_of_a_year(weekdays, count):
    """E6: the ticked days of every week of 1990, each once, in order."""
    dates = _in_year(1990, frequency.occurrences(
        date(1990, 1, 1), frequency.WEEKS, weekdays=weekdays))

    assert len(dates) == count
    assert dates == sorted(set(dates))


def test_every_two_weeks_on_two_weekdays():
    """E7: every 2 weeks on Monday and Thursday, from a Wednesday."""
    dates = _first(4, frequency.occurrences(
        date(1990, 1, 3), frequency.WEEKS, 2, weekdays=[0, 3]))

    assert dates == [date(1990, 1, 4), date(1990, 1, 15),
                     date(1990, 1, 18), date(1990, 1, 29)]


def test_days():
    """E8: a daily crosses the end of a year; every 10 days steps by 10."""
    daily = _first(3, frequency.occurrences(date(1990, 12, 30),
                                            frequency.DAYS))
    every_ten = _first(3, frequency.occurrences(date(1990, 1, 1),
                                                frequency.DAYS, 10))

    assert daily == [date(1990, 12, 30), date(1990, 12, 31),
                     date(1991, 1, 1)]
    assert every_ten == [date(1990, 1, 1), date(1990, 1, 11),
                         date(1990, 1, 21)]


def test_days_through_a_leap_day():
    """E8: a daily of a leap year comes out on February 29."""
    daily = _first(3, frequency.occurrences(date(1992, 2, 28),
                                            frequency.DAYS))

    assert daily == [date(1992, 2, 28), date(1992, 2, 29),
                     date(1992, 3, 1)]


def test_every_five_months_across_the_end_of_a_year():
    """E2, E3: the months go on into the next years, the day clamped."""
    dates = _first(4, frequency.occurrences(date(1990, 11, 30),
                                            frequency.MONTHS, 5))

    assert dates == [date(1990, 11, 30), date(1991, 4, 30),
                     date(1991, 9, 30), date(1992, 2, 29)]


def test_the_dates_end_with_2099():
    """E9: no date is given after 2099-12-31, whatever the unit."""
    months = list(frequency.occurrences(date(2099, 12, 1),
                                        frequency.MONTHS))
    days = list(frequency.occurrences(date(2099, 12, 30), frequency.DAYS))
    weeks = list(frequency.occurrences(date(2099, 12, 28), frequency.WEEKS,
                                       weekdays=[0, 1, 2, 3, 4, 5, 6]))

    assert months == [date(2099, 12, 1)]
    assert days == [date(2099, 12, 30), date(2099, 12, 31)]
    assert weeks == [date(2099, 12, day) for day in range(28, 32)]


@pytest.mark.parametrize('unit', frequency.UNITS)
def test_a_huge_interval_ends_without_an_error(unit):
    """E9: an interval that leaps past 2099 stops after the first date."""
    dates = list(frequency.occurrences(date(1990, 1, 1), unit, 10 ** 9))

    assert dates == [date(1990, 1, 1)]


@pytest.mark.parametrize('unit, interval', [
    (frequency.MONTHS, 0),
    (frequency.DAYS, -1),
    ('years', 1),
])
def test_a_wrong_rule_is_refused(unit, interval):
    """E10: an interval below 1 or an unknown unit raises ValueError."""
    with pytest.raises(ValueError):
        frequency.occurrences(date(1990, 1, 1), unit, interval)
