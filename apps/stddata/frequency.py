"""
The days on which a periodical comes out, from a first date and a rule:
every n days, every n weeks on some weekdays, or every n months.
"""

import calendar
from datetime import date

from apps.stddata.gcddates import LAST_YEAR

DAYS, WEEKS, MONTHS = 'days', 'weeks', 'months'
UNITS = (DAYS, WEEKS, MONTHS)

# No date is given past the last day of the last year of a key date.
_LAST_ORDINAL = date(LAST_YEAR, 12, 31).toordinal()


def occurrences(first, unit, interval=1, weekdays=()):
    """
    Return a generator of the dates of a rule, in order, from first on.

    unit is DAYS, WEEKS or MONTHS, interval the number of units from one
    date to the next. For WEEKS, weekdays are numbers from 0 (Monday) to
    6, as date.weekday() gives them; with none, the weekday of first is
    used. For MONTHS, a day that a month does not have gives the last day
    of that month. No date is past the end of LAST_YEAR. Raise ValueError
    at once for an interval below 1 or an unknown unit.
    """
    if interval < 1:
        raise ValueError('The interval must be 1 or more.')
    if unit == DAYS:
        return _days(first, interval)
    if unit == WEEKS:
        return _weeks(first, interval, weekdays)
    if unit == MONTHS:
        return _months(first, interval)
    raise ValueError('Unknown unit: %r' % (unit,))


def _days(first, interval):
    """Yield first and then the day every interval days."""
    for ordinal in range(first.toordinal(), _LAST_ORDINAL + 1, interval):
        yield date.fromordinal(ordinal)


def _weeks(first, interval, weekdays):
    """
    Yield the weekdays of the weeks 0, interval, 2 x interval...

    Week 0 is the week, Monday to Sunday, of first; the days of it that
    come before first are left out.
    """
    days = sorted(set(weekdays)) or [first.weekday()]
    start = first.toordinal()
    for monday in range(start - first.weekday(), _LAST_ORDINAL + 1,
                        7 * interval):
        for weekday in days:
            ordinal = monday + weekday
            if start <= ordinal <= _LAST_ORDINAL:
                yield date.fromordinal(ordinal)


def _months(first, interval):
    """
    Yield the day of first in the months 0, interval, 2 x interval...

    In a month too short for that day, the last day of the month is
    taken: a monthly keeps twelve dates a year.
    """
    start = first.year * 12 + first.month - 1
    for index in range(start, (LAST_YEAR + 1) * 12, interval):
        year, month = divmod(index, 12)
        last_day = calendar.monthrange(year, month + 1)[1]
        yield date(year, month + 1, min(first.day, last_day))
