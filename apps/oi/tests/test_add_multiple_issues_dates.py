"""The dates of the issues added several at a time, and their list."""
import re
from decimal import Decimal
from html.parser import HTMLParser

import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import CreditType
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi import states
from apps.oi.forms import get_bulk_issue_revision_form, IssueDateRowForm
from apps.oi.models import CTYPES, Changeset, IssueRevision
from apps.stddata.models import Date, Language, Script

METHODS = ['number', 'volume', 'year', 'year_volume']

# The fields of each add form at 53568040, in their order, for a series
# without an end year (issue.py, the ordering lists and
# _shared_key_order).
SHARED_FIELDS = [
  'indicia_publisher', 'indicia_pub_not_printed',
  'brand_emblem', 'no_brand',
  'indicia_frequency', 'no_indicia_frequency',
  'price', 'page_count', 'page_count_uncertain',
  'editing', 'no_editing',
  'indicia_printer', 'indicia_printer_not_printed',
  'indicia_printer_sourced_by',
  'no_isbn', 'no_barcode',
  'rating', 'no_rating', 'comments',
  'publisher_id', 'year_began']
FIELDS_OF_TODAY = {
  'number': ['after', 'number_of_issues', 'first_number',
             'volume', 'display_volume_with_number', 'no_volume'],
  'volume': ['after', 'number_of_issues', 'first_number',
             'first_volume', 'issues_per_volume'],
  'year': ['after', 'number_of_issues',
           'first_number', 'first_year', 'issues_per_year',
           'volume', 'display_volume_with_number', 'no_volume'],
  'year_volume': ['after', 'number_of_issues',
                  'first_number', 'first_year', 'first_volume',
                  'issues_per_cycle', 'display_volume_with_number'],
}

DATE_KEYS = ['dates_help', 'first_date', 'date_interval', 'date_unit',
             'date_weekdays', 'date_pattern', 'date_month_names']

# The plain values of a revision compared field by field.
REVISION_FIELDS = [
  'number', 'title', 'no_title', 'volume', 'no_volume',
  'volume_not_printed', 'display_volume_with_number', 'variant_name',
  'publication_date', 'key_date', 'year_on_sale', 'month_on_sale',
  'day_on_sale', 'on_sale_date_uncertain', 'indicia_frequency',
  'no_indicia_frequency', 'price', 'page_count', 'page_count_uncertain',
  'editing', 'no_editing', 'notes', 'keywords', 'indicia_pub_not_printed',
  'no_brand', 'indicia_printer_not_printed', 'indicia_printer_sourced_by',
  'isbn', 'no_isbn', 'barcode', 'no_barcode', 'rating', 'no_rating',
  'revision_sort_code', 'date_inferred']

# What an add of 3 issues without dates saved at 53568040, besides the
# numbering of NUMBERED.
SAVED_OF_TODAY = {
  'title': '', 'no_title': False, 'volume_not_printed': False,
  'variant_name': '', 'publication_date': '', 'key_date': '',
  'year_on_sale': None, 'month_on_sale': None, 'day_on_sale': None,
  'on_sale_date_uncertain': False, 'indicia_frequency': 'monthly',
  'no_indicia_frequency': False, 'price': '1.00 USD',
  'page_count': Decimal('36.000'), 'page_count_uncertain': False,
  'editing': '', 'no_editing': False, 'notes': '', 'keywords': '',
  'indicia_pub_not_printed': False, 'no_brand': False,
  'indicia_printer_not_printed': False, 'indicia_printer_sourced_by': '',
  'isbn': '', 'no_isbn': False, 'barcode': '', 'no_barcode': False,
  'rating': 'all ages', 'no_rating': False, 'date_inferred': False,
  'indicia_publisher': 'Test Indicia Publisher',
  'brand_emblem': ['Test Brand '], 'indicia_printer': [], 'credits': [],
  'after': None}
# number, volume, no_volume, display_volume_with_number of the 3 issues.
NUMBERED = {
  'number': [('1', '', False, False), ('2', '', False, False),
             ('3', '', False, False)],
  'volume': [('1', '1', False, True), ('2', '1', False, True),
             ('3', '1', False, True)],
  'year': [('1/1990', '', False, False), ('2/1990', '', False, False),
           ('3/1990', '', False, False)],
  'year_volume': [('1/1990', '1', False, False), ('2/1990', '1', False, False),
                  ('3/1990', '1', False, False)],
}
# Wrong values left in the block of the dates with its first date empty:
# the block is empty, so none of them is looked at.
EMPTY_BLOCK_ERRORS = {'date_interval': '0', 'date_unit': 'years',
                      'date_weekdays': ['7'], 'date_pattern': '{year} ' * 20,
                      'date_month_names': 'x' * 401}


@pytest.fixture
def adding_client(client, any_indexer):
    """A client logged in as an indexer who can reserve."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


@pytest.fixture
def add_values(any_added_indicia_publisher, any_added_brand):
    """Values typed in the add forms besides the numbering."""
    return {
      'number_of_issues': '3',
      'indicia_publisher': str(any_added_indicia_publisher.id),
      'brand_emblem': str(any_added_brand.id),
      'indicia_frequency': 'monthly',
      'price': '1.00 USD',
      'page_count': '36',
      'rating': 'all ages',
      'comments': 'test',
    }


def _url(series, method='number'):
    """Return the address of an add form."""
    return reverse('add_multiple_issues',
                   kwargs={'series_id': series.id, 'method': method})


def _numbering(method):
    """Return what each add form needs besides the number of issues."""
    return {'number': {},
            'volume': {'issues_per_volume': '12'},
            'year': {'first_year': '1990', 'issues_per_year': '12'},
            'year_volume': {'first_year': '1990',
                            'issues_per_cycle': '12'}}[method]


class _FormReader(HTMLParser):
    """Read what a browser posts from the form sent to an address."""

    def __init__(self, action):
        """Read the form whose action, without its anchor, is action."""
        super().__init__(convert_charrefs=True)
        self.action = action
        self.inside = False
        self.values = {}
        self.select = None
        self.multiple = False
        self.first_option = None
        self.textarea = None

    def handle_starttag(self, tag, attrs):
        """Take the value of a control, as the browser would send it."""
        attrs = dict(attrs)
        if tag == 'form':
            self.inside = (attrs.get('action', '').split('#')[0] ==
                           self.action)
        if not self.inside or 'disabled' in attrs:
            return
        name = attrs.get('name')
        if tag == 'input' and name:
            kind = attrs.get('type', 'text')
            if kind in ('submit', 'button', 'image', 'reset', 'file'):
                return
            if kind in ('checkbox', 'radio') and 'checked' not in attrs:
                return
            default = 'on' if kind in ('checkbox', 'radio') else ''
            self.values.setdefault(name, []).append(
              attrs.get('value', default))
        elif tag == 'select' and name:
            self.select = name
            self.multiple = 'multiple' in attrs
            self.first_option = None
            self.values.setdefault(name, [])
        elif tag == 'option' and self.select:
            if self.first_option is None:
                self.first_option = attrs.get('value', '')
            if 'selected' in attrs:
                self.values[self.select].append(attrs.get('value', ''))
        elif tag == 'textarea' and name:
            self.textarea = name
            self.values[name] = ['']

    def handle_endtag(self, tag):
        """Close a form, a list or a text box."""
        if tag == 'form':
            self.inside = False
        elif tag == 'select' and self.select:
            # A single list with nothing selected sends its first choice.
            if (not self.values[self.select] and not self.multiple and
                    self.first_option is not None):
                self.values[self.select] = [self.first_option]
            self.select = None
        elif tag == 'textarea' and self.textarea:
            # The browser drops the line break that opens a text box.
            text = self.values[self.textarea][0]
            if text.startswith('\n'):
                self.values[self.textarea] = [text[1:]]
            self.textarea = None

    def handle_data(self, data):
        """Take the text of a text box."""
        if self.textarea:
            self.values[self.textarea][0] += data


def _rendered(response, action):
    """Return the values the form of a page sends, name by name."""
    reader = _FormReader(action)
    reader.feed(response.content.decode())
    return reader.values


def _post(client, response, action, changes, button='add'):
    """Post the form of a page as rendered, with some values changed."""
    data = _rendered(response, action)
    for name, value in changes.items():
        data[name] = value if isinstance(value, list) else [value]
    data[button] = ['']
    return client.post(action, data)


def _shape_of_850(series, method, add_values):
    """Return a post without the date keys, as the tests of #850 send."""
    data = dict(add_values, **_numbering(method))
    data.update({
      'publisher_id': series.publisher.id,
      'year_began': series.year_began,
      'issue_credit_revisions-TOTAL_FORMS': 0,
      'issue_credit_revisions-INITIAL_FORMS': 0,
    })
    return data


def _saved(revision):
    """Return the values of a new issue revision, field by field."""
    values = {name: getattr(revision, name) for name in REVISION_FIELDS}
    values['indicia_publisher'] = (revision.indicia_publisher.name
                                   if revision.indicia_publisher else None)
    values['brand_emblem'] = sorted(
      revision.brand_emblem.values_list('name', flat=True))
    values['indicia_printer'] = sorted(
      revision.indicia_printer.values_list('name', flat=True))
    values['credits'] = list(revision.issue_credit_revisions.values_list(
      'creator__name', 'credit_type__name'))
    values['after'] = revision.after
    return values


def _new_revisions(series):
    """Return the issue revisions added to a series, in their order."""
    return list(IssueRevision.objects.filter(series=series, issue=None)
                .order_by('revision_sort_code'))


@pytest.mark.django_db
@pytest.mark.parametrize('method', METHODS)
def test_add_forms_keep_the_fields_of_today(
      adding_client, any_added_series, method):
    """V1: the fields of today stay, in the order of today."""
    response = adding_client.get(_url(any_added_series, method))

    fields = list(response.context['form'].fields)
    assert ([name for name in fields if name not in DATE_KEYS] ==
            FIELDS_OF_TODAY[method] + SHARED_FIELDS)
    assert fields == FIELDS_OF_TODAY[method] + DATE_KEYS + SHARED_FIELDS


@pytest.mark.django_db
@pytest.mark.parametrize('shape', ['rendered', '850', 'wrong block'])
@pytest.mark.parametrize('method', METHODS)
def test_add_without_dates_saves_what_it_saved_before(
      adding_client, any_added_series, add_values, method, shape):
    """V3: with the first date empty the add saves what it saved before."""
    series = any_added_series
    action = _url(series, method)
    if shape == '850':
        response = adding_client.post(
          action, _shape_of_850(series, method, add_values))
    else:
        values = dict(add_values, **_numbering(method))
        if shape == 'wrong block':
            values.update(EMPTY_BLOCK_ERRORS)
        response = _post(adding_client, adding_client.get(action), action,
                         values)

    assert response.status_code == 302
    assert response['Location'] == reverse('editing')
    changeset = Changeset.objects.get(change_type=CTYPES['issue_add'],
                                      issuerevisions__series=series,
                                      issuerevisions__revision_sort_code=0)
    assert changeset.state == states.PENDING
    revisions = _new_revisions(series)
    assert [revision.changeset_id for revision in revisions] == \
        [changeset.id] * 3
    for position, revision in enumerate(revisions):
        number, volume, no_volume, with_number = NUMBERED[method][position]
        assert _saved(revision) == dict(
          SAVED_OF_TODAY, number=number, volume=volume, no_volume=no_volume,
          display_volume_with_number=with_number,
          revision_sort_code=position)
        assert (revision.publication_date, revision.key_date) == ('', '')


# The fields of the bulk edit form at 53568040, in their order.
BULK_EDIT_FIELDS_OF_TODAY = (
  ['no_title', 'volume', 'display_volume_with_number', 'no_volume',
   'volume_not_printed'] + SHARED_FIELDS[:6] +
  ['publication_date', 'key_date'] + SHARED_FIELDS[6:])

ENGLISH = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December']
# The texts of twelve monthlies from 1990-01-15, written as
# '{month} {year}'.
MONTHLY = [('%s 1990' % name, '1990-%02d-00' % month)
           for month, name in enumerate(ENGLISH, 1)]

DATES_DO_NOT_FIT = ('The dates do not fit: they go past the year 2099 or '
                    'too many dates are left out.')
KEY_DATE_EMPTY = 'Dates are present, but the key date is empty.'
NO_DAY_NOTE = ('These dates have no day: issues of the same month, or of '
               'the same year, get the same text and key date.')
NOT_A_CHOICE = 'Select a valid choice. %s is not one of the available choices.'


def _dated(add_values, method='number', **changes):
    """Return the values of V4: 12 issues, monthly from 1990-01-15."""
    values = dict(add_values, number_of_issues='12', first_date='1990-01-15',
                  **_numbering(method))
    values.update(changes)
    return values


def _list(client, series, add_values, method='number', **changes):
    """Fill in the block of the dates and select Submit: the list."""
    action = _url(series, method)
    return _post(client, client.get(action), action,
                 _dated(add_values, method, **changes))


def _rows(response, action):
    """Return the rows of the list of a page as the page sends them."""
    values = _rendered(response, action)
    return [{'day': values['dates-%d-day' % row][0],
             'publication_date': values['dates-%d-publication_date' % row][0],
             'key_date': values['dates-%d-key_date' % row][0],
             'skip': 'dates-%d-skip' % row in values}
            for row in range(int(values['dates-TOTAL_FORMS'][0]))]


def _texts(rows):
    """Return the publication date and key date of each row."""
    return [(row['publication_date'], row['key_date']) for row in rows]


def _words(response):
    """Return the text of a page with its runs of spaces made one."""
    return ' '.join(response.content.decode().split())


def _form_action(response, action):
    """Return the address, anchor included, of the form sent to action."""
    return [address for address in re.findall(
              r'<form action="([^"]*)"', response.content.decode())
            if address.split('#')[0] == action][0]


def _saved_dates(series):
    """Return the two dates of each new issue revision, in order."""
    return [(revision.publication_date, revision.key_date)
            for revision in _new_revisions(series)]


def _counts():
    """Return the number of changes and of issue revisions."""
    return Changeset.objects.count(), IssueRevision.objects.count()


def _compare_page(client, series):
    """Return the compare page of the add, with plain line breaks."""
    changeset = _new_revisions(series)[0].changeset
    response = client.get(reverse('compare', kwargs={'id': changeset.id}))
    return response.content.decode().replace('\r\n', '\n')


@pytest.mark.django_db
def test_bulk_edit_has_no_date_fields(any_added_series):
    """V2: the bulk edit keeps its fields; the date fields are not there."""
    bulk_edit = get_bulk_issue_revision_form(any_added_series, 'bulk_edit')
    add = get_bulk_issue_revision_form(any_added_series, 'number')

    assert list(bulk_edit().fields) == BULK_EDIT_FIELDS_OF_TODAY
    assert set(DATE_KEYS) <= set(add().fields)


@pytest.mark.django_db
@pytest.mark.parametrize('method', METHODS)
def test_first_submit_with_dates_shows_the_list(
      adding_client, any_added_series, add_values, method):
    """V4, V6: the first Submit with a first date shows the list only."""
    before = _counts()

    response = _list(adding_client, any_added_series, add_values, method)

    assert response.status_code == 200
    rows = _rows(response, _url(any_added_series, method))
    assert [row['day'] for row in rows] == ['1990-%02d-15' % month
                                            for month in range(1, 13)]
    assert _texts(rows) == MONTHLY
    assert not any(row['skip'] for row in rows)
    assert '12 issues, from 1990-01-15 to 1990-12-15.' in _words(response)
    assert _counts() == before


class _LabelReader(HTMLParser):
    """Read the labels of a page and the ids of its controls."""

    def __init__(self):
        """Start with no label and no control."""
        super().__init__(convert_charrefs=True)
        self.labels = {}
        self.ids = {}
        self.label = None

    def handle_starttag(self, tag, attrs):
        """Note a control by name, or open a label."""
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name'):
            self.ids[attrs['name']] = attrs.get('id')
        elif tag == 'label':
            self.label = attrs.get('for')
            self.labels[self.label] = ''

    def handle_endtag(self, tag):
        """Close a label."""
        if tag == 'label':
            self.label = None

    def handle_data(self, data):
        """Take the text of a label."""
        if self.label is not None:
            self.labels[self.label] += data


@pytest.mark.django_db
def test_each_control_of_the_list_has_a_label(
      adding_client, any_added_series, add_values):
    """Each box and tick of the list has a label with its purpose and day,
    for a screen reader."""
    page = _list(adding_client, any_added_series, add_values)
    reader = _LabelReader()
    reader.feed(page.content.decode())

    for row, month in enumerate(range(1, 13)):
        day = '1990-%02d-15' % month
        for name, words in [('publication_date', 'Publication date of'),
                            ('key_date', 'Keydate of'),
                            ('skip', 'No issue on')]:
            control = reader.ids['dates-%d-%s' % (row, name)]
            assert control
            assert ' '.join(reader.labels.get(control, '').split()) == \
                '%s %s' % (words, day)


@pytest.mark.django_db
@pytest.mark.parametrize('method', METHODS)
def test_list_posted_as_rendered_saves_its_dates(
      adding_client, any_added_series, add_values, method):
    """V5, V6: the list posted as shown saves its dates, in order."""
    action = _url(any_added_series, method)
    page = _list(adding_client, any_added_series, add_values, method)

    response = _post(adding_client, page, action, {})

    assert response.status_code == 302
    assert _saved_dates(any_added_series) == MONTHLY
    revisions = _new_revisions(any_added_series)
    assert revisions[0].changeset.state == states.PENDING


@pytest.mark.django_db
def test_preview_dates_shows_the_list_and_saves_nothing(
      adding_client, any_added_series, add_values):
    """V7: Preview Dates shows the list, pressed twice too, saving nothing."""
    action = _url(any_added_series)
    before = _counts()

    first = _post(adding_client, adding_client.get(action), action,
                  _dated(add_values), button='preview')
    second = _post(adding_client, first, action, {}, button='preview')

    for page in (first, second):
        assert page.status_code == 200
        assert _texts(_rows(page, action)) == MONTHLY
    assert _counts() == before


@pytest.mark.django_db
def test_form_opens_at_the_list_only_when_there_is_one(
      adding_client, any_added_series, add_values):
    """The address of the form ends in #dates-preview only on a page with
    the list: an add without dates keeps the address of today."""
    action = _url(any_added_series)
    empty = adding_client.get(action)

    with_list = _list(adding_client, any_added_series, add_values)
    with_errors = _post(adding_client, empty, action,
                        dict(add_values, number_of_issues=''))

    assert _form_action(empty, action) == action
    assert _form_action(with_list, action) == action + '#dates-preview'
    assert 'dates-TOTAL_FORMS' not in _rendered(with_errors, action)
    assert _form_action(with_errors, action) == action


@pytest.mark.django_db
@pytest.mark.parametrize('weekdays', [[], ['2']])
def test_weekly_dates_of_a_year(adding_client, any_added_series, add_values,
                                weekdays):
    """V8: 52 weeklies from Wednesday 1990-01-03, ticked or not."""
    action = _url(any_added_series)

    page = _list(adding_client, any_added_series, add_values,
                 number_of_issues='52', first_date='1990-01-03',
                 date_unit='weeks', date_weekdays=weekdays,
                 date_pattern='{day} {month} {year}')

    rows = _rows(page, action)
    assert len(rows) == 52
    assert rows[-1] == {'day': '1990-12-26',
                        'publication_date': '26 December 1990',
                        'key_date': '1990-12-26', 'skip': False}


@pytest.mark.django_db
@pytest.mark.parametrize('unit', ['weeks', 'days'])
def test_dates_without_a_day_get_a_note(adding_client, any_added_series,
                                        add_values, unit):
    """Days or weeks written without {day}: a note above the list, which
    is saved as before."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values,
                 number_of_issues='5', first_date='1990-01-03',
                 date_unit=unit)

    words = _words(page)
    assert NO_DAY_NOTE in words
    assert words.index(NO_DAY_NOTE) < words.index('Keydate')
    response = _post(adding_client, page, action, {})

    assert response.status_code == 302
    assert _saved_dates(any_added_series) == \
        [('January 1990', '1990-01-00')] * 5


@pytest.mark.django_db
@pytest.mark.parametrize('changes', [
  {},
  {'date_unit': 'weeks', 'date_pattern': '{day} {month} {year}'},
  {'date_unit': 'days', 'date_pattern': '{day} {month} {year}'}])
def test_dates_with_a_day_or_monthly_have_no_note(
      adding_client, any_added_series, add_values, changes):
    """Months, or days and weeks written with {day}: the list, no note."""
    page = _list(adding_client, any_added_series, add_values, **changes)

    assert len(_rows(page, _url(any_added_series))) == 12
    assert 'These dates have no day' not in _words(page)


@pytest.mark.django_db
def test_corrected_date_is_saved_as_typed(adding_client, any_added_series,
                                          add_values):
    """V9: a corrected date stays through Preview Dates and is saved."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)

    page = _post(adding_client, page, action,
                 {'dates-1-publication_date': 'February-March 1990'},
                 button='preview')
    assert _rows(page, action)[1]['publication_date'] == \
        'February-March 1990'
    response = _post(adding_client, page, action, {})

    assert response.status_code == 302
    assert _saved_dates(any_added_series)[:3] == [
      ('January 1990', '1990-01-00'),
      ('February-March 1990', '1990-02-00'),
      ('March 1990', '1990-03-00')]


@pytest.mark.django_db
def test_date_ticked_no_issue_moves_the_issues_on(
      adding_client, any_added_series, add_values):
    """V10: a date ticked No issue moves the next issues to later dates."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    before = _counts()

    page = _post(adding_client, page, action, {'dates-1-skip': 'on'})

    assert page.status_code == 200
    assert _counts() == before
    rows = _rows(page, action)
    assert len(rows) == 13
    assert [row['skip'] for row in rows] == [False, True] + [False] * 11
    issues = [(day, revision.number)
              for row, day, revision in page.context['dates_rows']
              if revision is not None]
    assert (issues[1][0].isoformat(), str(issues[1][1])) == \
        ('1990-03-15', '2')
    assert _texts(rows)[-1] == ('January 1991', '1991-01-00')
    assert '12 issues, from 1990-01-15 to 1991-01-15.' in _words(page)

    response = _post(adding_client, page, action, {})

    assert response.status_code == 302
    assert _saved_dates(any_added_series) == \
        MONTHLY[:1] + MONTHLY[2:] + [('January 1991', '1991-01-00')]


@pytest.mark.django_db
def test_tick_sent_as_zero_reads_the_same_everywhere(
      adding_client, any_added_series, add_values):
    """A tick sent as '0' is a tick both where the list is compared and
    where its dates are taken: the list comes back with the tick, nothing
    is saved, and posted as shown the issues leave that date out."""
    row = IssueDateRowForm({'day': '1990-02-15', 'skip': '0'})
    assert row.is_valid()
    assert (row['skip'].value(), row.cleaned_data['skip']) == (True, True)
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    before = _counts()

    page = _post(adding_client, page, action, {'dates-1-skip': '0'})

    assert page.status_code == 200
    assert _counts() == before
    assert [row['skip'] for row in _rows(page, action)] == \
        [False, True] + [False] * 11
    response = _post(adding_client, page, action, {'dates-1-skip': '0'})
    assert response.status_code == 302
    assert _saved_dates(any_added_series) == \
        MONTHLY[:1] + MONTHLY[2:] + [('January 1991', '1991-01-00')]


@pytest.mark.django_db
@pytest.mark.parametrize('change, texts', [
  ({'number_of_issues': '10'}, MONTHLY[:10]),
  ({'date_pattern': '{day} {month} {year}'},
   [('15 %s 1990' % name, '1990-%02d-15' % month)
    for month, name in enumerate(ENGLISH, 1)])])
def test_changed_form_shows_the_list_again(
      adding_client, any_added_series, add_values, change, texts):
    """V11: a form changed after its list shows a new list, saves nothing."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    before = _counts()

    response = _post(adding_client, page, action, change)

    assert response.status_code == 200
    assert _texts(_rows(response, action)) == texts
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('change, field, error', [
  ({'dates-0-key_date': 'abc'}, 'key_date', 'Enter a valid value.'),
  ({'dates-0-key_date': ''}, '__all__', KEY_DATE_EMPTY)])
def test_wrong_row_is_shown_with_its_error(
      adding_client, any_added_series, add_values, change, field, error):
    """V12: a row with a wrong date is shown again with its error."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    before = _counts()

    response = _post(adding_client, page, action, change)

    assert response.status_code == 200
    assert response.context['dates_formset'][0].errors[field] == [error]
    assert error in response.content.decode()
    assert _rows(response, action)[0]['key_date'] == change['dates-0-key_date']
    assert _counts() == before


@pytest.mark.django_db
def test_ticked_row_is_not_checked(adding_client, any_added_series,
                                   add_values):
    """V12: the texts of a row ticked No issue are kept, not checked."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    page = _post(adding_client, page, action,
                 {'dates-0-key_date': 'abc', 'dates-0-skip': 'on'})
    assert _rows(page, action)[0] == {
      'day': '1990-01-15', 'publication_date': 'January 1990',
      'key_date': 'abc', 'skip': True}

    response = _post(adding_client, page, action, {})

    assert response.status_code == 302
    assert _saved_dates(any_added_series) == \
        MONTHLY[1:] + [('January 1991', '1991-01-00')]


@pytest.mark.django_db
def test_rows_without_publication_date_are_accepted(
      adding_client, any_added_series, add_values):
    """V13: a key date alone, no dates, and dots in a key date."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)

    response = _post(adding_client, page, action, {
      'dates-0-publication_date': '',
      'dates-1-publication_date': '', 'dates-1-key_date': '',
      'dates-2-key_date': '1990.01.00'})

    assert response.status_code == 302
    assert _saved_dates(any_added_series)[:3] == [
      ('', '1990-01-00'), ('', ''), ('March 1990', '1990-01-00')]


@pytest.mark.django_db
def test_date_block_errors_are_on_their_fields(any_added_series):
    """V14: the checks of the block put their errors on their fields."""
    form_class = get_bulk_issue_revision_form(any_added_series, 'number')
    data = {'number_of_issues': '401',
            'publisher_id': any_added_series.publisher.id,
            'first_date': '1690-01-01', 'date_interval': '1',
            'date_unit': 'months', 'date_pattern': '{month}',
            'date_month_names': ', '.join(ENGLISH[:11])}

    form = form_class(data)

    assert not form.is_valid()
    assert form.errors['first_date'] == [
      'The first date must be in the years 1700 to 2099.']
    assert form.errors['date_pattern'] == ['Include {year}.']
    assert form.errors['date_month_names'] == [
      'Enter the twelve month names, separated by commas.']
    assert form.errors['number_of_issues'] == [
      'With dates, at most 400 issues can be added at a time.']
    form = form_class(dict(data, number_of_issues='12',
                           first_date='1990-01-01', date_interval='',
                           date_unit='', date_pattern='{month} {year}',
                           date_month_names=', '.join(ENGLISH)))
    assert not form.is_valid()
    assert form.errors['date_interval'] == ['This field is required.']
    assert form.errors['date_unit'] == ['This field is required.']
    assert form_class(dict(data, first_date='')).is_valid()


@pytest.mark.django_db
def test_preview_without_first_date_asks_for_it(
      adding_client, any_added_series, add_values):
    """V15: Preview Dates without a first date asks for it."""
    action = _url(any_added_series)
    before = _counts()

    response = _post(adding_client, adding_client.get(action), action,
                     add_values, button='preview')

    assert response.status_code == 200
    assert response.context['form'].errors['first_date'] == [
      'Enter the first date to preview the dates.']
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('code, read, first', [('it', str.lower, 'gennaio'),
                                               ('XZZ', str, 'January')])
def test_month_names_follow_the_language_of_the_series(
      adding_client, any_added_series, code, read, first):
    """V16: the month names are proposed in the language of the series."""
    series = any_added_series
    series.language = Language.objects.get_or_create(
      code=code, defaults={'name': code})[0]
    series.save()
    action = _url(series)

    names = _rendered(adding_client.get(action),
                      action)['date_month_names'][0].split(', ')

    assert len(names) == 12
    assert read(names[0]) == first


@pytest.mark.django_db
def test_dates_past_2099_are_refused(adding_client, any_added_series,
                                     add_values):
    """V17: dates that go past 2099 give an error and save nothing."""
    before = _counts()

    response = _list(adding_client, any_added_series, add_values,
                     first_date='2099-06-01')

    assert response.status_code == 200
    assert response.context['form'].errors['first_date'] == [
      DATES_DO_NOT_FIT]
    assert 'dates-TOTAL_FORMS' not in _rendered(
      response, _url(any_added_series))
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('change', [
  {'dates-0-day': 'x'},
  {'dates-%d-day' % row: '1990-%02d-16' % (row + 1) for row in range(12)}])
def test_tampered_list_is_shown_again(adding_client, any_added_series,
                                      add_values, change):
    """V18: a list that is not the list of the form is made again."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    before = _counts()

    response = _post(adding_client, page, action, change)

    assert response.status_code == 200
    assert [row['day'] for row in _rows(response, action)] == \
        ['1990-%02d-15' % month for month in range(1, 13)]
    assert _counts() == before


@pytest.mark.django_db
@pytest.mark.parametrize('field, value, error', [
  ('date_weekdays', '7', NOT_A_CHOICE % '7'),
  ('date_weekdays', '-1', NOT_A_CHOICE % '-1'),
  ('date_weekdays', 'x', NOT_A_CHOICE % 'x'),
  ('date_interval', '0', 'Ensure this value is greater than or equal to 1.'),
  ('date_interval', '1.5', 'Enter a whole number.')])
def test_tampered_rule_is_refused_on_its_field(
      adding_client, any_added_series, add_values, field, value, error):
    """A weekday or an interval that the form does not offer is refused
    on its field before any date is made; nothing is saved."""
    before = _counts()

    response = _list(adding_client, any_added_series, add_values,
                     date_unit='weeks', **{field: value})

    assert response.status_code == 200
    assert response.context['form'].errors[field] == [error]
    assert 'dates-TOTAL_FORMS' not in _rendered(
      response, _url(any_added_series))
    assert _counts() == before


@pytest.mark.django_db
def test_compare_page_shows_the_dates(adding_client, any_added_series,
                                      add_values):
    """V19: the approver sees the two dates of each new issue."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    _post(adding_client, page, action, {})

    content = _compare_page(adding_client, any_added_series)

    assert '<th> Publication Date </th>\n  <th> Key Date </th>' in content
    for publication_date, key_date in MONTHLY:
        assert '<td> %s\n  <td> %s\n' % (publication_date, key_date) \
            in content
    assert 'publication date, key date and notes' not in content
    assert 'Keep in mind\nthat notes will always be blank.' in content


@pytest.mark.django_db
def test_compare_page_of_an_add_without_dates(
      adding_client, any_added_series, add_values):
    """V20: the compare page of an add without dates is that of today."""
    adding_client.post(_url(any_added_series), _shape_of_850(
      any_added_series, 'number', add_values))

    content = _compare_page(adding_client, any_added_series)

    assert 'Publication Date' not in content
    assert '<tr>\n  <th> Volume </th>' in content
    assert '<th> Display Number </th>\n  <th> Preview </th>' in content
    assert ('Keep in mind\nthat publication date, key date and notes will '
            'always be blank.\n</p>') in content


@pytest.mark.django_db
def test_compare_page_spaces_the_cells_of_the_dated_issues(
      adding_client, any_added_series, add_values):
    """The cells of the table of the dated issues on the compare page are
    spaced apart, as on the other tables of the change pages."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    _post(adding_client, page, action, {})

    content = _compare_page(adding_client, any_added_series)

    assert '<tr class="[&>th]:px-1.5">\n  <th> Volume </th>' in content
    assert content.count('<tr class="[&>td]:px-1.5">\n  <td> ') == 12


# What the credits row of the add form shows when it is checked with
# nothing in it: no creator, no credit description, and the credit type
# taken away by its form.
EMPTY_CREDIT_ERRORS = ['This field is required.',
                       'This field cannot be null.']
CREDIT_ROW = 'issue_credit_revisions-0-'


@pytest.fixture
def editing_credit_type():
    """The credit type of the credits of an issue: the only choice of the
    list of the credits row, which a browser posts."""
    return CreditType.objects.get_or_create(
      id=CREDIT_TYPES['editing'],
      defaults={'name': 'editing', 'sort_code': CREDIT_TYPES['editing']})[0]


def _creator_name(name):
    """Return a creator name to credit, of a creator of its own."""
    return CreatorNameDetail.objects.create(
      name=name, in_script=Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0],
      creator=Creator.objects.create(
        gcd_official_name=name, sort_name=name,
        birth_date=Date.objects.create()))


@pytest.mark.django_db
@pytest.mark.parametrize('button, dated, shown', [
  ('preview', True, '12 issues, from 1990-01-15 to 1990-12-15.'),
  ('add', True, '12 issues, from 1990-01-15 to 1990-12-15.'),
  ('preview', False, 'Enter the first date to preview the dates.')])
def test_untouched_credits_row_shows_no_errors(
      adding_client, any_added_series, add_values, editing_credit_type,
      button, dated, shown):
    """The page shown again by the dates has no error on the credits row
    the person left untouched, though its credit type is posted."""
    action = _url(any_added_series)
    page = adding_client.get(action)
    assert _rendered(page, action)[CREDIT_ROW + 'credit_type'] == \
        [str(editing_credit_type.id)]

    response = _post(adding_client, page, action,
                     _dated(add_values) if dated else add_values,
                     button=button)

    assert response.status_code == 200
    assert shown in _words(response)
    for error in EMPTY_CREDIT_ERRORS:
        assert error not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('credit, field, error', [
  ({}, 'credit_name', 'This field is required.'),
  ({'credit_name': 'associate editor', 'credited_as': 'Some Name'},
   '__all__',
   'Is credited needs to be selected when entering a name as credited.')])
def test_filled_credit_is_checked_when_the_issues_are_submitted(
      adding_client, any_added_series, add_values, editing_credit_type,
      credit, field, error):
    """A credit filled in on the page of the list is checked when the
    issues are submitted: its error is shown and nothing is saved."""
    action = _url(any_added_series)
    page = _list(adding_client, any_added_series, add_values)
    before = _counts()
    credit = dict(credit, creator=str(_creator_name('Some Editor').id))

    response = _post(adding_client, page, action, {
      CREDIT_ROW + name: value for name, value in credit.items()})

    assert response.status_code == 200
    assert response.context['credits_formset'][0].errors[field] == [error]
    assert error in response.content.decode()
    assert _counts() == before
