"""
The dates of an issue as GCD writes them.

The publication date is a text written as it is printed on the issue,
from a written form such as '{month} {year}' and the month names of the
series. The key date is YYYY-MM-DD, with 00 for the month or the day when
the publication date does not give it.
"""

# The years a key date can have (the validator of IssueRevision.key_date).
FIRST_YEAR, LAST_YEAR = 1700, 2099

# The precision of a written date: what a key date keeps of the day.
YEAR, MONTH, DAY = 'year', 'month', 'day'

_PLACEHOLDERS = ('{day}', '{month}', '{year}')


def pattern_error(pattern):
    """
    Return '' if a written form can be used, else the reason it cannot.

    A form must hold {year}; {day} needs {month}; no brace may be left
    once {day}, {month} and {year} are taken out. The form is split at
    them, not shortened, so that two pieces never join into a placeholder.
    """
    if '{year}' not in pattern:
        return 'Include {year}.'
    if '{day}' in pattern and '{month}' not in pattern:
        return 'Include {month} when {day} is used.'
    pieces = [pattern]
    for placeholder in _PLACEHOLDERS:
        pieces = [part for piece in pieces
                  for part in piece.split(placeholder)]
    if any('{' in piece or '}' in piece for piece in pieces):
        return 'Only {day}, {month} and {year} can be written in braces.'
    return ''


def pattern_precision(pattern):
    """Return DAY for a form with {day}, else MONTH with {month}, else YEAR."""
    if '{day}' in pattern:
        return DAY
    if '{month}' in pattern:
        return MONTH
    return YEAR


def publication_date(day, pattern, month_names):
    """
    Write the publication date of a day in a written form.

    {day} becomes the day without a leading zero, {month} the name of the
    month in month_names (twelve names, January first) and {year} the
    year; the rest of the form is kept as typed. The form is typed by a
    user, so it is never run through str.format. The month name goes in
    last: a name is typed too and is never searched for placeholders.
    """
    text = pattern.replace('{day}', str(day.day))
    text = text.replace('{year}', str(day.year))
    return text.replace('{month}', month_names[day.month - 1])


def key_date(day, precision=DAY):
    """
    Return the key date of a day: YYYY-MM-DD, YYYY-MM-00 or YYYY-00-00.

    The precision says what is kept of the day. Raise ValueError for a
    year outside FIRST_YEAR-LAST_YEAR or an unknown precision.
    """
    if not FIRST_YEAR <= day.year <= LAST_YEAR:
        raise ValueError('A key date must be in the years %d-%d.'
                         % (FIRST_YEAR, LAST_YEAR))
    if precision == DAY:
        return '%04d-%02d-%02d' % (day.year, day.month, day.day)
    if precision == MONTH:
        return '%04d-%02d-00' % (day.year, day.month)
    if precision == YEAR:
        return '%04d-00-00' % day.year
    raise ValueError('Unknown precision: %r' % (precision,))
