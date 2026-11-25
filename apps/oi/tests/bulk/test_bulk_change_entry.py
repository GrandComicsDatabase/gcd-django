"""Start of a bulk change: the link on lists, the selection, the preview."""
from html import unescape
from importlib import import_module
from types import SimpleNamespace
from urllib.parse import urljoin

import pytest

from django.contrib.auth.models import AnonymousUser, Permission
from django.test import RequestFactory
from django.urls import reverse
from django.utils.html import strip_tags
from haystack.query import SearchQuerySet

from apps.gcd.models import IndiciaPublisher, Issue, Publisher, Series
from apps.gcd.models.issue import IssuePublisherTable
from apps.gcd.views.details import (
    TW_SORT_TABLE_TEMPLATE, generic_sortable_list)
from apps.indexer.models import Error
from apps.mycomics.models import Collector, ConditionGradeScale
from apps.oi import bulk, states
from apps.oi.forms.bulk import REVISION_FORMS, offered_fields
from apps.oi.forms.issue import (
    IssueRevisionForm, get_issue_revision_form)
from apps.oi.models import (
    Changeset, IssueRevision, RevisionLock, CTYPES, _get_revision_lock,
    get_issue_field_list)
from apps.oi.tests.bulk.page_forms import PageForms
from apps.select.views import store_select_data

SEARCH = {'target': 'issue', 'method': 'iexact', 'logic': 'False',
          'series': 'Series for Issues'}
LINK = 'Use all objects of this list for a'


@pytest.fixture
def indexer(any_indexer, any_language):
    """An indexer with the collector that a confirmed account gets."""
    Collector.objects.create_collector(
      any_indexer,
      grade_system=ConditionGradeScale.objects.create(name='Test scale'),
      default_language=any_language)
    return any_indexer


@pytest.fixture
def reserving_indexer(indexer):
    """An indexer who may reserve changes."""
    indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    return indexer


@pytest.fixture
def started(client, settings, reserving_indexer, approved_issues):
    """
    Turn bulk changes on, start one from the advanced search of the three
    approved issues and return a function that gets its page with GET
    parameters.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    response = client.get(reverse('process_advanced_search'),
                          dict(SEARCH, _export='bulk'))
    assert response.status_code == 302
    url, token = response['Location'].split('?token=')

    def get(**params):
        return client.get(url, dict(params, token=token))
    return get


def _preview(started, name, **params):
    """Get the preview of an operation on the field name."""
    return started(field=name, shown=name, **params).context['bulk_preview']


def test_fields_of_the_edit_form_have_a_policy():
    """Each field is either changed or excluded, and no other is named."""
    policy = set(bulk.policy_fields(IssueRevision))
    excluded = {name for names in bulk.EXCLUDED[IssueRevision].values()
                for name in names}
    fields = set(IssueRevision._get_regular_fields()) | \
        set(get_issue_field_list())
    assert not policy & excluded
    assert policy | excluded == fields
    assert policy <= set(REVISION_FORMS[IssueRevision].base_fields)
    turned_off = {name for names in bulk.TURNED_OFF_BY[Issue][1].values()
                  for name in names}
    assert turned_off <= policy


@pytest.mark.django_db
@pytest.mark.parametrize('user, enabled, shown, legacy', [
    ('anonymous', True, False, False),
    ('indexer', True, False, False),
    ('reserving_indexer', False, False, True),
    ('reserving_indexer', True, True, False),
])
def test_link_on_a_list(client, settings, request, any_added_issue, user,
                        enabled, shown, legacy):
    """Only an indexer who may reserve sees the link, and only if on."""
    settings.BULK_CHANGE_ENABLED = enabled
    if user != 'anonymous':
        client.force_login(request.getfixturevalue(user))

    response = client.get(reverse('process_advanced_search'), SEARCH)

    content = response.content.decode()
    assert (LINK in content) is shown
    assert ('_export=bulk' in content) is shown
    assert (reverse('edit_issues_in_bulk') in content) is legacy


@pytest.mark.django_db
def test_link_is_one_button_above_the_list(client, settings,
                                           reserving_indexer,
                                           any_added_issue):
    """
    The list shows the link once, above its rows, as a button that
    holds the whole sentence.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)

    content = client.get(reverse('process_advanced_search'),
                         SEARCH).content.decode()

    at = content.index('_export=bulk')
    link = content[content.rindex('<a ', 0, at):content.index('</a>', at)]
    assert content.count('_export=bulk') == 1
    assert at < content.index('sortable_heading')
    assert 'class="btn-blue-editing inline-block visited:text-black"' in link
    assert ' '.join(strip_tags(link).split()) == LINK + ' bulk change'


@pytest.mark.django_db
def test_no_link_on_a_list_with_a_json_download(settings,
                                                reserving_indexer,
                                                approved_issues):
    """
    A list whose page offers its own JSON download shows that button
    and no link, and its address with _export=bulk shows the list and
    starts no bulk change.
    """
    settings.BULK_CHANGE_ENABLED = True
    contents = []
    for query in ({}, {'_export': 'bulk'}):
        request = RequestFactory().get('/list/', query)
        request.user = reserving_indexer
        request.session = import_module(
          settings.SESSION_ENGINE).SessionStore()
        items = Issue.objects.all()
        table = IssuePublisherTable(items,
                                    template_name=TW_SORT_TABLE_TEMPLATE)

        response = generic_sortable_list(
          request, items, table, 'gcd/search/tw_generic_list_sortable.html',
          {'item_name': 'issue', 'plural_suffix': 's',
           'json_download_url': '/download/'})

        assert response.status_code == 200
        assert not table.bulk_change
        assert bulk.SELECTION_KEY not in request.session
        contents.append(response.content.decode())

    assert 'Download: (JSON)' in contents[0]
    assert '_export=bulk' not in contents[0]


@pytest.mark.django_db
def test_no_link_on_a_select_list(client, settings, reserving_indexer,
                                  any_added_issue):
    """A list for picking an object has no link, and no entry either."""
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    session = client.session
    store_select_data(SimpleNamespace(session=session), 'key', {'issue': True})
    session.save()
    url = reverse('select_object_search_htmx', kwargs={'select_key': 'key'})
    query = {'search_object': 'issue',
             'publisher_auto': any_added_issue.series.publisher_id}

    response = client.get(url, query)
    export = client.get(url, dict(query, _export='bulk'))

    assert any_added_issue.number in response.content.decode()
    assert LINK not in response.content.decode()
    assert export.status_code == 200
    assert bulk.SELECTION_KEY not in client.session


@pytest.mark.django_db
@pytest.mark.parametrize('name, value', [
    (None, None), ('MYCOMICS', True), ('NO_OI', True),
    ('BULK_CHANGE_ENABLED', False)])
def test_entry_needs_a_list_of_issues(settings, reserving_indexer,
                                      any_added_issue, name, value):
    """Only Django lists of a target model qualify, on an editing site."""
    settings.BULK_CHANGE_ENABLED = True
    if name:
        setattr(settings, name, value)
    allowed = name is None

    assert bulk.entry_allowed(reserving_indexer,
                              Issue.objects.all()) is allowed
    assert not bulk.entry_allowed(reserving_indexer, Series.objects.all())
    assert not bulk.entry_allowed(reserving_indexer, SearchQuerySet())
    assert not bulk.entry_allowed(AnonymousUser(), Issue.objects.all())


@pytest.mark.django_db
@pytest.mark.parametrize('no_export, no_bulk_edit, empty, shown', [
    (False, False, False, True), (True, False, False, False),
    (False, True, False, False), (False, False, True, False)])
def test_link_needs_an_exportable_list_with_objects(
      settings, reserving_indexer, approved_issues, no_export, no_bulk_edit,
      empty, shown):
    """
    A list without downloads, one that its page keeps from bulk edits, or
    one without objects has no link.
    """
    settings.BULK_CHANGE_ENABLED = True
    request = RequestFactory().get('/list/')
    request.user = reserving_indexer
    items = Issue.objects.none() if empty else Issue.objects.all()
    table = IssuePublisherTable(items,
                                template_name=TW_SORT_TABLE_TEMPLATE)
    table.no_export = no_export

    generic_sortable_list(request, items, table,
                          'gcd/search/tw_generic_list_sortable.html',
                          {'item_name': 'issue', 'plural_suffix': 's',
                           'no_bulk_edit': no_bulk_edit})

    assert table.bulk_change is shown


@pytest.mark.django_db
def test_selection_keeps_the_filters(client, settings, reserving_indexer,
                                     approved_issues):
    """The selection is the filtered list, and its link keeps the query."""
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)

    response = client.get(reverse('process_advanced_search'),
                          dict(SEARCH, issues='43,44', _export='bulk'))
    page = client.get(response['Location'])

    selection = client.session[bulk.SELECTION_KEY]
    assert selection['ids'] == [issue.id for issue in approved_issues[1:]]
    assert 'issues=43%2C44' in selection['source']
    assert '_export' not in selection['source']
    assert page.context['selection'] == '2 issues'
    assert 'href="%s"' % selection['source'].replace('&', '&amp;') in \
        page.content.decode()


@pytest.mark.django_db
def test_selection_has_distinct_ids_without_deleted(settings,
                                                    reserving_indexer,
                                                    approved_issues):
    """Each object counts once, in id order; deleted ones are left out."""
    approved_issues[0].deleted = True
    approved_issues[0].save()
    request = RequestFactory().get('/list/', {'_export': 'bulk'})
    request.user = reserving_indexer
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()
    # One row for each issue of the series of each issue: duplicates.
    items = Issue.objects.filter(series__issue__isnull=False) \
                         .order_by('-id')

    response = bulk.start_from_list(request, items)

    assert response.status_code == 302
    assert request.session[bulk.SELECTION_KEY]['ids'] == \
        [issue.id for issue in approved_issues[1:]]


@pytest.mark.django_db
def test_selection_of_a_list_without_query(settings, reserving_indexer,
                                           approved_issues):
    """The link to a list without a query is its path alone."""
    settings.BULK_CHANGE_ENABLED = True
    request = RequestFactory().get('/list/', {'_export': 'bulk'})
    request.user = reserving_indexer
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()

    bulk.start_from_list(request, Issue.objects.all())

    assert request.session[bulk.SELECTION_KEY]['source'] == '/list/'


@pytest.mark.django_db
def test_a_list_address_keeps_its_escapes(client, settings,
                                          reserving_indexer, approved_issues):
    """
    The address of the list is kept escaped, as get_full_path gives it: a
    line break in a free segment of the path stays %0A, so that it cannot
    add lines to the record of the bulk change.  A colon needs no escape in
    a path, so %3A comes back as the same address with a plain colon.
    """
    settings.BULK_CHANGE_ENABLED = True
    Issue.objects.filter(id__in=[issue.id for issue in approved_issues]) \
                 .update(barcode='9781234567897')
    client.force_login(reserving_indexer)
    path = '/barcode/9781234567897/sort/alpha%0ACheckpoint%3A%20never%0Ax/'
    kept = '/barcode/9781234567897/sort/alpha%0ACheckpoint:%20never%0Ax/'

    response = client.get(path + '?_export=bulk')
    page = client.get(response['Location'])

    source = client.session[bulk.SELECTION_KEY]['source']
    assert source == kept
    assert '\n' not in source
    assert 'href="%s"' % kept in page.content.decode()


@pytest.mark.django_db
def test_selection_above_the_maximum(client, settings, reserving_indexer,
                                     approved_issues):
    """A list longer than BULK_CHANGE_MAX gives an error page."""
    settings.BULK_CHANGE_ENABLED = True
    settings.BULK_CHANGE_MAX = 2
    client.force_login(reserving_indexer)

    response = client.get(reverse('process_advanced_search'),
                          dict(SEARCH, _export='bulk'))

    assert response.status_code == 200
    assert 'at most 2 objects, and this list has 3' in \
        response.content.decode()
    assert bulk.SELECTION_KEY not in client.session


@pytest.mark.django_db
def test_selection_keeps_the_ids_that_were_counted(settings,
                                                   reserving_indexer,
                                                   approved_issues,
                                                   monkeypatch):
    """
    The selection holds the objects that were checked against
    BULK_CHANGE_MAX: one that joins the list after the check is left out.
    """
    settings.BULK_CHANGE_ENABLED = True
    settings.BULK_CHANGE_MAX = 2
    late = approved_issues[0]
    late.deleted = True
    late.save()
    request = RequestFactory().get('/list/', {'_export': 'bulk'})
    request.user = reserving_indexer
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()
    escape = bulk.escape_uri_path

    def join_then_escape(path):
        """Bring the deleted issue back into the list, then escape path."""
        Issue.objects.filter(id=late.id).update(deleted=False)
        return escape(path)
    monkeypatch.setattr(bulk, 'escape_uri_path', join_then_escape)

    response = bulk.start_from_list(request, Issue.objects.all())

    assert response.status_code == 302
    assert request.session[bulk.SELECTION_KEY]['ids'] == \
        [issue.id for issue in approved_issues[1:]]


def _counts():
    """Count the changes, locks and errors."""
    return [model.objects.count()
            for model in (Changeset, RevisionLock, Error)]


@pytest.mark.django_db
@pytest.mark.parametrize('open_changes', [0, 1])
def test_pages_write_nothing(client, settings, reserving_indexer,
                             approved_issues, open_changes):
    """
    The list, the page and the preview write no change, lock or error,
    also for an indexer who holds all the open changes allowed.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    for count in range(open_changes):
        Changeset.objects.create(indexer=reserving_indexer,
                                 state=states.OPEN,
                                 change_type=CTYPES['issue'])
    if open_changes:
        reserving_indexer.indexer.max_reservations = open_changes
        reserving_indexer.indexer.save()
    allowed = reserving_indexer.indexer.can_reserve_another()
    assert allowed is (not open_changes)
    counts = _counts()

    start = client.get(reverse('process_advanced_search'),
                       dict(SEARCH, _export='bulk'))
    url, token = start['Location'].split('?token=')
    page = client.get(url, {'token': token, 'field': 'price',
                            'shown': 'price', 'old_value': '=0.10 USD',
                            'operation': 'replace_exact',
                            'new_value': '0.12 USD'})

    assert page.context['bulk_preview']['changed'] == 3
    assert 'bg-preview' not in page.content.decode()
    assert counts == _counts()


@pytest.mark.django_db
def test_old_value_says_when_it_counts(started):
    """A field with two operations says that one ignores the old value."""
    note = 'Used only with Replace the old value.'

    assert note in started(field='price').content.decode()
    assert note not in started(field='rating').content.decode()


@pytest.mark.django_db
def test_field_lists_its_values(started):
    """The page lists the values of the chosen field, with counts."""
    form = started(field='price').context['form']

    assert form.fields['old_value'].choices == \
        [('=0.10 USD', '"0.10 USD" (3)')]


@pytest.mark.django_db
def test_values_keep_spaces_and_case(started, approved_issues, monkeypatch):
    """
    Values differing only in case or a space are three values; the page
    lists at most LISTED_VALUES of them and counts the others.
    """
    for issue, rating in zip(approved_issues,
                             ('Superhero', 'superhero', 'Superhero ')):
        Issue.objects.filter(id=issue.id).update(rating=rating)

    page = started(field='rating')
    monkeypatch.setattr(bulk, 'LISTED_VALUES', 2)
    shorter = started(field='rating')

    assert sorted(label for key, label
                  in page.context['form'].fields['old_value'].choices) == \
        ['"Superhero " (1)', '"Superhero" (1)', '"superhero" (1)']
    assert len(shorter.context['form'].fields['old_value'].choices) == 2
    assert shorter.context['more_values'] == 1
    assert '1 more value not listed' in shorter.content.decode()


@pytest.mark.django_db
def test_old_values_with_line_breaks(started, approved_issues):
    """
    A browser reads a line break in an attribute as LF and sends it as
    CRLF, so the key of a value holds none: each value with a line break
    is chosen as itself, and apart from one with a backslash.
    """
    values = ('A\nB', 'A\r\nB', 'A\\nB')
    for issue, value in zip(approved_issues, values):
        Issue.objects.filter(id=issue.id).update(price=value)
    keys = dict(started(field='price').context['form']
                .fields['old_value'].choices)

    for issue, value in zip(approved_issues, values):
        key = bulk.value_key(value)
        sent = key.replace('\r\n', '\n').replace('\r', '\n') \
                  .replace('\n', '\r\n')
        response = started(field='price', shown='price',
                           operation='replace_exact', old_value=sent,
                           new_value='0.12 USD')

        assert response.context['form'].cleaned_data['old_value'] == value
        assert [row[0] for row
                in response.context['bulk_preview']['rows']] == [issue]
        assert key in keys
        assert '\r' not in key and '\n' not in key


@pytest.mark.django_db
def test_transcribed_field_is_only_replaced(started):
    """A transcribed value is replaced one value at a time, never set."""
    rating = started(field='rating').context['form']
    price = started(field='price').context['form']

    assert [key for key, label in rating.fields['operation'].choices] == \
        ['replace_exact']
    assert [key for key, label in price.fields['operation'].choices] == \
        ['replace_exact', 'set']


@pytest.mark.django_db
def test_a_date_is_only_replaced(started):
    """
    A date belongs to each object: it is replaced, never set for all;
    a value that objects share may be set.
    """
    def operations(name):
        form = started(field=name).context['form']
        assert form.name == name
        return [key for key, label in form.fields['operation'].choices]

    for name in ('key_date', 'publication_date'):
        assert operations(name) == ['replace_exact']
    for name in ('price', 'volume', 'page_count', 'no_barcode'):
        assert operations(name) == ['replace_exact', 'set']


@pytest.mark.django_db
def test_preview_leaves_out_reserved_objects(started, approved_issues,
                                             any_approver):
    """An object that another change reserves is listed, not changed."""
    other = Changeset.objects.create(indexer=any_approver, state=states.OPEN,
                                     change_type=CTYPES['issue'])
    _get_revision_lock(approved_issues[1], other)

    preview = _preview(started, 'price', old_value='=0.10 USD',
                       operation='replace_exact', new_value='0.10  USD')

    assert preview['changed'] == 2
    assert preview['reserved'] == [approved_issues[1]]
    assert [row[0] for row in preview['rows']] == \
        [approved_issues[0], approved_issues[2]]
    assert "<span class='added'>\u00a0</span>" in preview['rows'][0][2]


@pytest.mark.django_db
def test_preview_leaves_out_turned_off_fields(started, approved_issues):
    """
    A field that the series turns off is listed, not changed, where its
    value would change: the first issue has no rating already.
    """
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_rating=False)

    preview = _preview(started, 'no_rating', operation='set',
                       new_value='on')

    assert preview['changed'] == 0
    assert preview['turned_off'] == approved_issues[1:]


@pytest.mark.django_db
@pytest.mark.parametrize('chosen, value, changed', [
    ({'field': 'price', 'operation': 'replace_exact',
      'old_value': '=0.10 USD', 'new_value': '0.12 USD'}, '0.12 USD', 3),
    ({'field': 'no_isbn', 'operation': 'set', 'new_value': 'on'}, True, 2),
])
def test_forms_as_rendered(client, settings, reserving_indexer,
                           approved_issues, chosen, value, changed):
    """
    The link of the list and the forms of the page, followed and
    submitted as rendered with the choices of the indexer, give the
    preview; no page repeats an id.  The first issue has "no isbn"
    already.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    url = reverse('edit_issues_in_bulk')
    search = reverse('process_advanced_search')
    page = PageForms(client.get(search, SEARCH).content.decode())
    # The list links to itself with a query string.
    start = client.get(urljoin(search, page.link('_export=bulk')))
    response = client.get(start['Location'])
    for step in ({'field': chosen['field']}, chosen):
        page = PageForms(response.content.decode())
        assert page.repeated_ids() == []
        response = client.get(url, page.data(page.form('GET', url), **step))

    assert PageForms(response.content.decode()).repeated_ids() == []
    assert response.context['form'].cleaned_data['new_value'] == value
    assert response.context['bulk_preview']['changed'] == changed


@pytest.mark.django_db
@pytest.mark.parametrize('name, params, stored', [
    ('price', {'operation': 'set', 'new_value': ' 0.12 USD '}, '0.12 USD'),
    ('price', {'operation': 'set', 'new_value': '0.12 USD; '}, '0.12 USD'),
    ('key_date', {'operation': 'replace_exact', 'old_value': '=1947-01-00',
                  'new_value': '1947.02.00'}, '1947-02-00'),
])
def test_preview_shows_the_value_as_stored(started, approved_issues, name,
                                           params, stored):
    """
    The new value is cleaned as in the edit form, which drops the outer
    spaces and a ';' at the end of a price and writes a key date with
    dashes, and shown so.  A key date is only replaced, so the three
    issues first get the same one.
    """
    Issue.objects.filter(id__in=[issue.id for issue in approved_issues]) \
                 .update(key_date='1947-01-00')

    response = started(field=name, shown=name, **params)

    assert response.context['form'].cleaned_data['new_value'] == stored
    preview = response.context['bulk_preview']
    assert preview['changed'] == 3
    assert unescape(strip_tags(preview['rows'][0][2])) == stored


@pytest.mark.django_db
@pytest.mark.parametrize('params, error', [
    ({'operation': 'replace_exact', 'new_value': '1950-01-00'},
     'Please choose the old value.'),
    ({'operation': 'replace_exact', 'old_value': '=1947-01-00',
      'new_value': ''},
     'The new value of Key Date cannot be empty.'),
    ({'operation': 'replace_exact', 'old_value': '=1947-01-00',
      'new_value': '   '},
     'The new value of Key Date cannot be empty.'),
])
def test_operation_errors(started, params, error):
    """Replacing needs an old value; a key date is never emptied."""
    response = started(field='key_date', shown='key_date', **params)

    assert 'bulk_preview' not in response.context
    assert response.context['form'].non_field_errors() == [error]


@pytest.mark.django_db
@pytest.mark.parametrize('name, new_value, label', [
    ('key_date', '1950-01-00', 'Key Date'),
    ('publication_date', 'January 1950', 'Publication Date'),
])
def test_an_empty_date_is_not_filled(started, approved_issues, name,
                                     new_value, label):
    """
    The empty value of a date is never replaced: it would give one date
    to every object without one.
    """
    Issue.objects.filter(id=approved_issues[0].id).update(**{name: ''})

    response = started(field=name, shown=name, operation='replace_exact',
                       old_value='=', new_value=new_value)

    assert 'bulk_preview' not in response.context
    assert response.context['form'].non_field_errors() == [
      'The old value of %s cannot be empty.' % label]


@pytest.mark.django_db
def test_changed_field_lists_its_values(started):
    """Choosing another field shows its values before any preview."""
    response = started(field='price', shown='rating',
                       operation='replace_exact', old_value='=')

    assert not response.context['form'].is_bound
    assert 'bulk_preview' not in response.context
    assert response.context['form'].fields['old_value'].choices == \
        [('=0.10 USD', '"0.10 USD" (3)')]


@pytest.mark.django_db
def test_preview_lists_objects_deleted_since_the_start(started,
                                                       approved_issues):
    """
    Issues deleted after the start are counted on the selection line;
    their values are not listed; the preview lists those it would have
    changed, and counts none.
    """
    Issue.objects.filter(id=approved_issues[0].id).update(price='0.20 USD',
                                                          deleted=True)
    Issue.objects.filter(id=approved_issues[1].id).update(deleted=True)

    page = started(field='price')
    preview = _preview(started, 'price', old_value='=0.10 USD',
                       operation='replace_exact', new_value='0.12 USD')

    assert '2 deleted since' in page.content.decode()
    assert page.context['form'].fields['old_value'].choices == [
      ('=0.10 USD', '"0.10 USD" (1)')]
    assert preview['changed'] == 1
    assert preview['deleted'] == [approved_issues[1]]


@pytest.mark.django_db
def test_key_date_pattern_of_the_model(started):
    """A key date that the pattern of the model refuses is an error."""
    form = started(field='key_date', shown='key_date',
                   operation='replace_exact', old_value='=1947-01-00',
                   new_value='Feb 1947').context['form']

    assert 'new_value' in form.errors


@pytest.mark.django_db
def test_edit_form_cleans_the_key_date_alike(any_added_series):
    """The edit form of an issue has the key date cleaning of the bulk."""
    form_class = get_issue_revision_form(any_added_series.publisher,
                                         series=any_added_series)

    assert form_class.clean_key_date is IssueRevisionForm.clean_key_date


@pytest.mark.django_db
def test_new_indicia_publisher_of_the_publisher(started, approved_issues,
                                                any_added_indicia_publisher,
                                                indicia_publisher_add_values,
                                                publisher_add_values):
    """
    The new indicia publisher is one of the publisher of the issues, as in
    their edit form; one of another publisher is refused.
    """
    values = {name: value for name, value in publisher_add_values.items()
              if name != 'keywords'}
    other_publisher = Publisher.objects.create(**dict(
      values, name='Other Publisher'))
    values = {name: value
              for name, value in indicia_publisher_add_values.items()
              if name != 'keywords'}
    other = IndiciaPublisher.objects.create(**dict(
      values, name='Other Indicia Publisher', parent=other_publisher))

    form = started(field='indicia_publisher', shown='indicia_publisher',
                   operation='set', new_value=other.id).context['form']
    choices = form.fields['new_value'].queryset

    assert 'new_value' in form.errors
    assert other not in choices
    assert any_added_indicia_publisher in choices


@pytest.mark.django_db
def test_link_fields_need_one_publisher(any_added_publisher):
    """A link to records of a publisher is offered only with one."""
    assert 'indicia_publisher' in offered_fields(IssueRevision,
                                                 any_added_publisher)
    assert 'indicia_publisher' not in offered_fields(IssueRevision, None)


@pytest.mark.django_db
@pytest.mark.parametrize('enabled', [True, False])
def test_unknown_selection(client, settings, reserving_indexer, enabled):
    """A selection the session lacks gives an error page, or off, none."""
    settings.BULK_CHANGE_ENABLED = enabled
    client.force_login(reserving_indexer)

    response = client.get(reverse('edit_issues_in_bulk'), {'token': 'old'})

    if enabled:
        assert 'no longer available' in response.content.decode()
    else:
        assert response.status_code == 302


@pytest.mark.django_db
def test_entry_needs_a_queryset(settings, reserving_indexer,
                                any_added_issue):
    """A raw query of issues, though of a target model, has no entry."""
    settings.BULK_CHANGE_ENABLED = True
    raw = Issue.objects.raw('SELECT * FROM gcd_issue')

    assert raw.model is Issue
    assert not bulk.entry_allowed(reserving_indexer, raw)


@pytest.mark.django_db
def test_list_of_deleted_objects_only(settings, reserving_indexer,
                                      approved_issues):
    """A list whose objects are all deleted gives an error page."""
    Issue.objects.filter(id__in=[issue.id for issue in approved_issues]) \
                 .update(deleted=True)
    request = RequestFactory().get('/list/', {'_export': 'bulk'})
    request.user = reserving_indexer
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()

    response = bulk.start_from_list(request, Issue.objects.all())

    assert 'This list has no objects for a bulk change.' in \
        response.content.decode()
    assert bulk.SELECTION_KEY not in request.session


@pytest.mark.django_db
def test_page_of_an_older_selection(started, client):
    """The token of an older selection gives an error page."""
    response = client.get(reverse('edit_issues_in_bulk'), {'token': 'old'})

    assert 'no longer available' in response.content.decode()


@pytest.mark.django_db
def test_page_after_every_object_was_deleted(started, approved_issues):
    """
    The page works when every object was deleted since the start, with
    no value to list and no field that needs one publisher.
    """
    Issue.objects.filter(id__in=[issue.id for issue in approved_issues]) \
                 .update(deleted=True)

    form = started(field='indicia_publisher').context['form']

    assert 'indicia_publisher' not in \
        [key for key, label in form.fields['field'].choices]
    assert form.fields['old_value'].choices == []


@pytest.mark.django_db
def test_deleted_object_of_another_publisher(started, approved_issues,
                                             publisher_add_values):
    """
    An issue of another publisher, deleted since the start, no longer
    keeps the fields that need one publisher away.
    """
    values = {name: value for name, value in publisher_add_values.items()
              if name != 'keywords'}
    other = Publisher.objects.create(**dict(values, name='Other Publisher'))
    series = Series.objects.get(id=approved_issues[2].series_id)
    series.pk = series.id = None
    series.publisher = other
    series.save()
    Issue.objects.filter(id=approved_issues[2].id).update(series=series,
                                                          deleted=True)

    form = started().context['form']

    assert 'indicia_publisher' in \
        [key for key, label in form.fields['field'].choices]


@pytest.mark.django_db
def test_values_by_count_with_hidden_spaces_shown(started,
                                                  approved_issues):
    """
    The most frequent value comes first; spaces that HTML would merge are
    no-break spaces, and no value at all is "(empty)".
    """
    for issue, price in zip(approved_issues, ('', '0.10  USD', '0.10  USD')):
        Issue.objects.filter(id=issue.id).update(price=price)

    form = started(field='price').context['form']

    assert form.fields['old_value'].choices == [
      ('=0.10  USD', '"0.10\u00a0\u00a0USD" (2)'), ('=', '(empty) (1)')]


@pytest.mark.django_db
def test_replace_leaves_other_values(started, approved_issues):
    """Replacing changes only the objects that hold the old value."""
    Issue.objects.filter(id=approved_issues[0].id).update(price='0.20 USD')

    preview = _preview(started, 'price', old_value='=0.10 USD',
                       operation='replace_exact', new_value='0.12 USD')

    assert preview['changed'] == 2
    assert [row[0] for row in preview['rows']] == approved_issues[1:]


@pytest.mark.django_db
def test_preview_follows_the_limit(started, settings):
    """The preview counts all changes and shows BULK_CHANGE_MAX of them."""
    settings.BULK_CHANGE_MAX = 2

    preview = _preview(started, 'price', old_value='=0.10 USD',
                       operation='replace_exact', new_value='0.12 USD')

    assert preview['changed'] == 3
    assert len(preview['rows']) == 2


@pytest.mark.django_db
def test_same_indicia_publisher_changes_nothing(started, approved_issues):
    """A link compares by its id: the same indicia publisher is no change."""
    current = approved_issues[0].indicia_publisher_id

    preview = _preview(started, 'indicia_publisher', operation='set',
                       new_value=current)

    assert preview['changed'] == 0


@pytest.mark.django_db
def test_unknown_operation_is_a_form_error(started):
    """A forged operation gives a form error, not a server error."""
    response = started(field='key_date', shown='key_date',
                       operation='forged', new_value='1950-01-00')

    assert 'operation' in response.context['form'].errors
    assert 'bulk_preview' not in response.context


@pytest.mark.django_db
def test_a_key_date_is_not_set_for_all(started):
    """Setting one key date for all is not a choice of the form."""
    response = started(field='key_date', shown='key_date', operation='set',
                       new_value='1950-01-00')

    assert response.context['form'].errors['operation'] == [
      'Select a valid choice. set is not one of the available choices.']
    assert 'bulk_preview' not in response.context


@pytest.mark.django_db
def test_preview_page_shows_rows_and_what_it_leaves_out(
      started, approved_issues, any_approver):
    """
    The page shows the rows of the changes and lists the objects left
    out: deleted since the start, reserved, or with the field off.
    """
    Issue.objects.filter(id=approved_issues[0].id).update(deleted=True)
    other = Changeset.objects.create(indexer=any_approver,
                                     state=states.OPEN,
                                     change_type=CTYPES['issue'])
    _get_revision_lock(approved_issues[1], other)

    content = started(field='price', shown='price',
                      old_value='=0.10 USD', operation='replace_exact',
                      new_value='0.12 USD').content.decode()
    Series.objects.filter(id=approved_issues[0].series_id) \
                  .update(has_rating=False)
    turned_off = started(field='no_rating', shown='no_rating',
                         operation='set', new_value='on').content.decode()

    assert 'Deleted since the list was chosen, so left out:' in content
    assert 'Reserved by other changes, so left out: 1' in content
    assert "0.1<span class='added'>2</span> USD" in content
    for issue in approved_issues:
        assert issue.get_absolute_url() in content
    assert 'Field turned off in their series, so left out:' in turned_off
