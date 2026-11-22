"""The publication dates of a series come from its earliest and latest
issue, by the year of the key dates."""
import pytest

from apps.stddata.models import Country, Language
from apps.gcd.models import Publisher, Series, Issue
from apps.gcd.models.series import SeriesTable

# Years of the series ('now': current), issues in sort order as
# (key date, publication date, optional 'variant' or 'deleted'), dates.
CASES = {
    'backwards': ((1973, 1975), [('1975-01-00', 'January 1975'),
                                 ('1973-05-00', 'May 1973'),
                                 ('1974-03-00', 'March 1974')],
                  'May 1973 - January 1975'),
    'end': ((1975, None), [('1975-01-00', 'January 1975'),
                           ('1977-05-00', 'May 1977'),
                           ('1976-03-00', 'March 1976'),
                           ('1975-10-00', 'October 1975')],
            'January 1975 - May 1977'),
    'current': ((1973, 'now'), [('1975-01-00', 'January 1975'),
                                ('1973-05-00', 'May 1973')],
                'May 1973 - present'),
    'undated earliest': ((1973, 1975), [('1975-01-00', 'January 1975'),
                                        ('1973-00-00', '')],
                         '1973 - January 1975'),
    'in order': ((1973, 1975), [('1973-05-00', 'May 1973'),
                                ('1974-03-00', 'March 1974'),
                                ('1975-01-00', 'January 1975')],
                 'May 1973 - January 1975'),
    'no key date': ((1973, 1975), [('', 'Spring 1974'),
                                   ('1973-05-00', 'May 1973'),
                                   ('1975-01-00', 'January 1975'),
                                   ('', 'Fall 1975')],
                    'Spring 1974 - Fall 1975'),
    'same year': ((1973, 1976), [('1975-12-00', 'December 1975'),
                                 ('1975-00-00', '1975')],
                  'December 1975 - 1975'),
    'variant': ((1973, 1976), [('1973-05-00', 'May 1973'),
                               ('1976-02-00', 'February 1976', 'variant'),
                               ('1974-03-00', 'March 1974')],
                'May 1973 - March 1974'),
    'deleted': ((1973, 1975), [('1974-03-00', 'March 1974'),
                               ('1973-05-00', 'May 1973', 'deleted'),
                               ('1975-01-00', 'January 1975')],
                'March 1974 - January 1975'),
    'outside years': ((1974, 1976), [('1975-03-00', 'March 1975'),
                                     ('1922-01-00', 'January 1922'),
                                     ('2026-05-00', 'May 2026'),
                                     ('1975-10-00', 'October 1975')],
                      'March 1975 - October 1975'),
}


@pytest.fixture
def publisher(db):
    """A publisher with the country and language its series need."""
    return Publisher.objects.create(
        name='Test Publisher', year_began=1970,
        country=Country.objects.get_or_create(
            id=904, defaults={'code': 'q5', 'name': 'Testland C'})[0])


def make_series(publisher, name):
    """Save the series of a case; its ends are the ends in sort order."""
    (began, ended), issues, _dates = CASES[name]
    series = Series.objects.create(
        name=name, sort_name=name, year_began=began,
        year_ended=None if ended == 'now' else ended,
        is_current=ended == 'now', publisher=publisher,
        country=publisher.country,
        language=Language.objects.get_or_create(
            id=904, defaults={'code': 'q6', 'name': 'Testish C'})[0])
    made = []
    for sort_code, (key_date, date, *flag) in enumerate(issues):
        made.append(Issue.objects.create(
            series=series, number=str(sort_code), sort_code=sort_code,
            key_date=key_date, publication_date=date,
            deleted=flag == ['deleted'],
            variant_of=made[0] if flag == ['variant'] else None))
    series.first_issue, series.last_issue = made[0], made[-1]
    series.issue_count = len([issue for issue in issues if len(issue) == 2])
    series.save()
    return series


@pytest.mark.parametrize('path', ['series page', 'list'])
@pytest.mark.parametrize('name', CASES)
def test_publication_dates(publisher, name, path):
    """The series page and a list row show the same dates."""
    series = make_series(publisher, name)
    if path == 'series page':
        shown = Series.objects.get(pk=series.pk).display_publication_dates()
    else:
        table = SeriesTable(Series.objects.filter(pk=series.pk))
        shown = next(iter(table.rows)).get_cell('published')
    assert shown == CASES[name][2]


@pytest.mark.parametrize('name, most', [
    ('in order', 0), ('no key date', 0), ('current', 1), ('backwards', 2)])
def test_a_list_reads_issues_only_when_the_years_leave_room(
        publisher, django_assert_max_num_queries, name, most):
    """A list row reads the issues of its series only if the series begins
    before its first issue or ends after its last one, once per side."""
    make_series(publisher, name)
    table = SeriesTable(Series.objects.filter(publisher=publisher)
                        .select_related('first_issue', 'last_issue'))
    with django_assert_max_num_queries(1 + most):
        shown = [row.get_cell('published') for row in table.rows]
    assert shown == [CASES[name][2]]


def test_a_current_series_does_not_read_its_last_issue(
        publisher, django_assert_num_queries):
    """A list that does not join the issues to its rows reads the first
    issue of a current series and its issues once, not its last issue."""
    make_series(publisher, 'current')
    table = SeriesTable(Series.objects.filter(publisher=publisher))
    with django_assert_num_queries(3):
        shown = [row.get_cell('published') for row in table.rows]
    assert shown == [CASES['current'][2]]
