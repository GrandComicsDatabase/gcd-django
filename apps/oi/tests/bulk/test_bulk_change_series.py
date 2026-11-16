"""A bulk change of series: the format fields of up to 100 series."""
from html import unescape
from itertools import count
from types import SimpleNamespace

import pytest

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import OperationalError, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import strip_tags

from apps.gcd.models import (
    Character, CharacterNameDetail, Creator, CreatorNameDetail, CreditType,
    Group, GroupNameDetail, Publisher, Series, StoryCharacter, StoryCredit,
    StoryGroup)
from apps.gcd.models.story import CREDIT_TYPES
from apps.indexer.models import Error, Indexer
from apps.oi import bulk, states
from apps.oi.forms.bulk import REVISION_FORMS, offered_fields
from apps.oi.forms.series import SeriesRevisionForm
from apps.oi.models import (
    Changeset, OngoingReservation, RevisionLock, SeriesRevision, CTYPES,
    _get_revision_lock, get_series_field_list)
from apps.oi.tests.bulk.invariants import check_invariants
from apps.oi.tests.bulk.test_bulk_change_open import (
    _made_long_ago, _operate, _remove, _sweep)
from apps.oi.tests.bulk.test_bulk_change_revert import _revert, _show, _words
from apps.select.views import store_select_data
from apps.stats.models import CountStats
from apps.stddata.models import Date, Script

TOKEN = 'series-token'
SOURCE = '/list/?binding=stitched'
FIELDS = ['color', 'dimensions', 'paper_stock', 'binding',
          'publishing_format']
BINDING = {'field': 'binding', 'shown': 'binding',
           'operation': 'replace_exact', 'old_value': '=Saddle-stitched',
           'new_value': 'saddle-stitched'}
COLOR = {'field': 'color', 'shown': 'color', 'operation': 'set',
         'new_value': 'black and white'}
BACK = dict(BINDING, old_value='=saddle-stitched',
            new_value='Saddle-stitched')
SERIES_SEARCH = {'target': 'series', 'method': 'icontains', 'logic': 'False',
                 'pub_name': 'Test Publisher', 'binding': 'stitched'}
LINK = 'Use all objects of this list for a'
REFUSED = 'A bulk change is changed only by its operations.'
SPACES = 'Spaces at the start or end of an old value are not restored.'
WAIT_WORDS = ('The publishers of these series are being saved at this '
              'moment, so nothing was changed. Please apply again.')


@pytest.fixture(autouse=True)
def invariants(db):
    """Start without applied tokens; check the invariants at the end."""
    cache.clear()
    yield
    check_invariants()


def _select(client, series, token=TOKEN):
    """Keep series as the selection of token, as a list would."""
    session = client.session
    session[bulk.SELECTION_KEY] = {
      'token': token, 'model': 'series', 'source': SOURCE,
      'ids': sorted(one.id for one in series)}
    session.save()


@pytest.fixture
def selection(client, settings, reserving_indexer, approved_series):
    """
    Turn bulk changes on, log the indexer in and keep the three approved
    series as the selection of TOKEN.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    _select(client, approved_series)
    return approved_series


@pytest.fixture
def make_change(client, selection, settings, reserving_indexer):
    """
    Return a function that makes an open bulk change as the page makes it,
    with the given operation, of the given series or of the three approved
    ones; its author is logged in.
    """
    settings.BULK_CHANGE_MAX_ACTIVE = 10
    reserving_indexer.indexer.max_reservations = 10
    reserving_indexer.indexer.save()
    tokens = count(1)

    def make(params=BINDING, series=None):
        token = 'series-token-%d' % next(tokens)
        _select(client, series or selection, token)
        response = _apply(client, token, **params)
        assert response.status_code == 302, _words(response)
        return Changeset.objects.filter(change_type=CTYPES['bulk']) \
                                .latest('id')
    return make


@pytest.fixture
def approved(make_change, approve_change):
    """The approved bulk change of the binding of the three series."""
    changeset = make_change()
    approve_change(changeset)
    return changeset


def _page(client, token=TOKEN, **params):
    """Get the bulk change page of token with GET parameters."""
    return client.get(reverse('edit_issues_in_bulk'),
                      dict(params, token=token))


def _apply(client, token=TOKEN, **params):
    """Post an operation, the binding by default, to the page of token."""
    return client.post(reverse('edit_issues_in_bulk') + '?token=' + token,
                       params or BINDING)


def _change():
    """The only bulk change."""
    return Changeset.objects.get(change_type=CTYPES['bulk'])


def _record(changeset):
    """The operation that the first comment of changeset records."""
    return bulk.operation_record(changeset)


def _compare(changeset):
    """The address of the page of changeset."""
    return reverse('compare', kwargs={'id': changeset.id})


def _values(series, name='binding'):
    """The stored values of the field name of series, in their order."""
    return [Series.objects.get(id=one.id).serializable_value(name)
            for one in series]


def _lock_of(series):
    """The lock of series, as a query."""
    return RevisionLock.objects.filter(
      content_type=ContentType.objects.get_for_model(Series),
      object_id=series.id)


def _approved(series, **values):
    """
    Change the stored values of series and of its latest approved
    revision, as an approved edit would have.
    """
    Series.objects.filter(id=series.id).update(**values)
    SeriesRevision.objects.filter(series=series, committed=True,
                                  next_revision=None).update(**values)


def _counts():
    """The numbers of the rows that a look at a page must not change."""
    return [model.objects.count()
            for model in (Changeset, RevisionLock, SeriesRevision, Error)]


def test_fields_of_the_series_form_have_a_policy():
    """
    The five format fields are changed, every other field of the series
    is left out for a reason, and nothing turns them off, joins them or
    keeps them from being emptied.
    """
    policy = set(bulk.policy_fields(SeriesRevision))
    excluded = {name for names in bulk.EXCLUDED[SeriesRevision].values()
                for name in names}
    fields = set(SeriesRevision._get_regular_fields()) | \
        set(get_series_field_list())

    assert policy == set(FIELDS)
    assert bulk.policy_fields(SeriesRevision) == dict.fromkeys(FIELDS, 'F')
    assert not policy & excluded
    assert policy | excluded == fields
    assert REVISION_FORMS[SeriesRevision] is SeriesRevisionForm
    assert offered_fields(SeriesRevision, None) == FIELDS
    assert bulk.BULK_TARGETS[Series] is SeriesRevision
    assert Series not in bulk.TURNED_OFF_BY
    assert SeriesRevision not in bulk.LOGICAL_FIELDS
    assert not policy & set(bulk.NOT_EMPTY)


@pytest.fixture
def series_list(approved_series, approved_stories, any_language):
    """
    Return a function that gives, for the name of a list of series, its
    address, its query and the ids of the series that it holds.  The
    creator, the character and the group appear in a sequence of the
    series of the approved issues, of the publisher of the series.
    """
    story = approved_stories[0]
    issue_series = story.issue.series
    publisher = issue_series.publisher

    def address(name):
        if name == 'publisher':
            return (reverse('show_publisher',
                            kwargs={'publisher_id': publisher.id}), {},
                    sorted([one.id for one in approved_series] +
                           [issue_series.id]))
        if name == 'current':
            current = [approved_series[0].id, approved_series[2].id]
            Series.objects.filter(id__in=current).update(is_current=True)
            return ('/publisher/%d/current_series/' % publisher.id, {},
                    current)
        if name == 'search':
            return (reverse('process_advanced_search'), SERIES_SEARCH,
                    [one.id for one in approved_series])
        if name == 'name':
            return (reverse('series_by_name',
                            kwargs={'series_name': 'Series'}), {},
                    sorted([one.id for one in approved_series] +
                           [issue_series.id]))
        if name == 'keyword':
            tagged = [approved_series[0], approved_series[2]]
            for one in tagged:
                one.keywords.add('Test Keyword')
            return (reverse('show_keyword',
                            kwargs={'keyword': 'Test Keyword',
                                    'model_name': 'series'}), {},
                    [one.id for one in tagged])
        if name == 'creator':
            creator = CreatorNameDetail.objects.create(
              name='Test Creator', is_official_name=True,
              creator=Creator.objects.create(
                gcd_official_name='Test Creator', sort_name='Test Creator',
                birth_date=Date.objects.create()),
              in_script=Script.objects.get_or_create(
                code='Tst', number=999, name='Test Script')[0])
            StoryCredit.objects.create(
              story=story, creator=creator,
              credit_type=CreditType.objects.get_or_create(
                id=CREDIT_TYPES['script'],
                defaults={'name': 'script', 'sort_code': 1})[0])
            url = reverse('creator_series',
                          kwargs={'creator_id': creator.creator_id})
        elif name == 'character':
            character = Character.objects.create(
              name='Test Character', disambiguation='', language=any_language,
              description='', notes='')
            StoryCharacter.objects.create(
              story=story, notes='',
              character=CharacterNameDetail.objects.create(
                name='Test Character', character=character,
                is_official_name=True))
            url = reverse('character_series',
                          kwargs={'character_id': character.id})
        else:
            group = Group.objects.create(
              name='Test Group', disambiguation='', language=any_language,
              description='', notes='')
            StoryGroup.objects.create(
              story=story, notes='',
              group_name=GroupNameDetail.objects.create(
                name='Test Group', group=group, is_official_name=True))
            url = reverse('group_series', kwargs={'group_id': group.id})
        return url, {}, [issue_series.id]
    return address


@pytest.mark.parametrize('name', ['publisher', 'current', 'creator',
                                  'character', 'group', 'search', 'name',
                                  'keyword'])
def test_every_list_of_series_starts_a_bulk_change(client, settings,
                                                   reserving_indexer,
                                                   series_list, name):
    """
    Each list of series offers the sentence to an indexer who may
    reserve, and its link keeps the series of the list as the selection,
    in id order, for the page of a bulk change of series.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    url, query, ids = series_list(name)

    page = client.get(url, query)
    start = client.get(url, dict(query, _export='bulk'))

    assert LINK in page.content.decode()
    assert start.status_code == 302
    assert start['Location'].startswith(
      reverse('edit_issues_in_bulk') + '?token=')
    selection = client.session[bulk.SELECTION_KEY]
    assert (selection['model'], selection['ids']) == ('series', ids)
    started = client.get(start['Location'])
    assert started.context['selection'] == '%d series' % len(ids)
    assert started.context['form'].name == 'color'


@pytest.mark.django_db
def test_no_entry_from_a_picking_list(client, settings, reserving_indexer,
                                      approved_series):
    """
    A list of series for picking an object has no link and no entry,
    though the same series have one on the page of their publisher.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)
    session = client.session
    store_select_data(SimpleNamespace(session=session), 'key',
                      {'series': True})
    session.save()
    url = reverse('select_object_search', kwargs={'select_key': 'key'})
    query = {'search_series': 'Search', 'series': 'Series',
             'publisher': 'Test Publisher', 'select_key': 'key'}
    publisher_page = reverse('show_publisher', kwargs={
      'publisher_id': approved_series[0].publisher_id})

    response = client.get(url, query)
    export = client.get(url, dict(query, _export='bulk'))

    assert LINK in client.get(publisher_page).content.decode()
    assert approved_series[2].name in response.content.decode()
    assert LINK not in response.content.decode()
    assert export.status_code == 200
    assert bulk.SELECTION_KEY not in client.session


def test_no_entry_with_bulk_changes_off(client, settings, reserving_indexer,
                                        approved_series):
    """The sentence and the entry of a list of series follow the switch."""
    client.force_login(reserving_indexer)
    url = reverse('process_advanced_search')

    settings.BULK_CHANGE_ENABLED = True
    shown = client.get(url, SERIES_SEARCH).content.decode()
    settings.BULK_CHANGE_ENABLED = False
    hidden = client.get(url, SERIES_SEARCH).content.decode()
    export = client.get(url, dict(SERIES_SEARCH, _export='bulk'))

    assert LINK in shown
    assert LINK not in hidden
    assert export.status_code == 200
    assert bulk.SELECTION_KEY not in client.session


def test_a_search_keeps_its_filter_in_the_record(client, settings,
                                                 reserving_indexer,
                                                 approved_series):
    """
    The selection of an advanced search of series keeps its filter, and
    the record of the change keeps the address of the list.
    """
    settings.BULK_CHANGE_ENABLED = True
    client.force_login(reserving_indexer)

    start = client.get(reverse('process_advanced_search'),
                       dict(SERIES_SEARCH, _export='bulk'))
    url, token = start['Location'].split('?token=')
    response = _apply(client, token=token)

    source = client.session[bulk.SELECTION_KEY]['source']
    assert 'binding=stitched' in source
    assert 'pub_name=Test+Publisher' in source
    assert '_export' not in source
    assert response.status_code == 302
    assert _record(_change())['source'].endswith(source)


def test_more_series_than_the_limit_are_refused(client, settings,
                                                reserving_indexer,
                                                approved_series):
    """A list of 101 series gives the error page of the limit."""
    settings.BULK_CHANGE_ENABLED = True
    settings.BULK_CHANGE_MAX = 100
    client.force_login(reserving_indexer)
    first = approved_series[0]
    Series.objects.bulk_create([
      Series(name='Extra %d' % number, sort_name='Extra %d' % number,
             year_began=1990, country=first.country, language=first.language,
             publisher=first.publisher, binding='Saddle-stitched')
      for number in range(98)])

    response = client.get(reverse('process_advanced_search'),
                          dict(SERIES_SEARCH, _export='bulk'))

    assert response.status_code == 200
    assert 'A bulk change can hold at most 100 objects, and this list has ' \
           '101.' in unescape(response.content.decode())
    assert bulk.SELECTION_KEY not in client.session


def test_page_offers_the_format_fields_in_form_order(client, selection):
    """The page offers the five fields, in the order of the edit form."""
    form = _page(client).context['form']

    assert [key for key, label in form.fields['field'].choices] == FIELDS
    assert form.name == 'color'
    assert form.fields['old_value'].choices == [
      ('=four colors', '"four colors" (3)')]


def test_values_keep_spaces_and_case(client, selection):
    """Values differing only in case or a space are three values."""
    for one, binding in zip(selection, ('Saddle-stitched', 'saddle-stitched',
                                        'Saddle-stitched ')):
        Series.objects.filter(id=one.id).update(binding=binding)

    form = _page(client, field='binding').context['form']

    assert sorted(label for key, label
                  in form.fields['old_value'].choices) == \
        ['"Saddle-stitched " (1)', '"Saddle-stitched" (1)',
         '"saddle-stitched" (1)']


@pytest.mark.parametrize('name', FIELDS)
def test_each_field_takes_both_operations(client, selection, name):
    """A value of a run of series is replaced, or set for all of them."""
    form = _page(client, field=name).context['form']

    assert form.name == name
    assert [key for key, label in form.fields['operation'].choices] == \
        ['replace_exact', 'set']


def test_new_value_is_cleaned_as_in_the_edit_form(client, selection):
    """The new value loses its outer spaces, as the edit form stores it."""
    response = _page(client, field='binding', shown='binding',
                     operation='set', new_value='  perfect bound ')

    assert response.context['form'].cleaned_data['new_value'] == \
        'perfect bound'
    preview = response.context['bulk_preview']
    assert preview['changed'] == 3
    assert unescape(strip_tags(preview['rows'][0][2])) == 'perfect bound'


def test_an_empty_new_value_clears_the_field(client, selection):
    """An empty new value is a value: it clears the field."""
    empty = dict(BINDING, new_value='')

    preview = _page(client, **empty).context['bulk_preview']
    response = _apply(client, **empty)

    assert preview['changed'] == 3
    assert response.status_code == 302
    assert {revision.binding
            for revision in _change().seriesrevisions.all()} == {''}


def test_pages_write_nothing(client, selection):
    """The page and its preview write no change, lock, revision or error."""
    before = _counts()

    listing = _page(client, field='binding')
    preview = _page(client, **BINDING).context['bulk_preview']

    assert listing.status_code == 200
    assert preview['changed'] == 3
    assert _counts() == before
    assert _values(selection) == ['Saddle-stitched'] * 3


def test_apply_makes_one_open_change(client, selection, reserving_indexer):
    """The changed series go into one OPEN change, which the page shows."""
    response = _apply(client)

    changeset = _change()
    assert response['Location'] == _compare(changeset)
    assert changeset.state == states.OPEN
    assert changeset.indexer == reserving_indexer
    revisions = changeset.seriesrevisions.order_by('series_id')
    assert [revision.series for revision in revisions] == selection
    assert {revision.binding for revision in revisions} == \
        {'saddle-stitched'}
    assert _values(selection) == ['Saddle-stitched'] * 3
    assert sorted(changeset.revision_locks.values_list('object_id',
                                                       flat=True)) == \
        [one.id for one in selection]
    lines = changeset.comments.get().text.split('\n')
    assert lines[0] == ('Operation: series.binding replace_exact '
                        '"Saddle-stitched" "saddle-stitched"')
    record = _record(changeset)
    assert record['source'].endswith(SOURCE)
    assert record['counts']['changed'] == 3
    words = _words(client.get(_compare(changeset)))
    assert '3 series' in words
    # The table marks the letter that changes, from the old to the new.
    assert 'Binding S addle-stitched s addle-stitched' in words


def test_only_the_series_that_change_are_locked(client, selection):
    """A series that keeps its value gets no revision and no lock."""
    Series.objects.filter(id=selection[1].id).update(binding='perfect bound')

    _apply(client)

    changeset = _change()
    assert [revision.series_id for revision
            in changeset.seriesrevisions.order_by('series_id')] == \
        [selection[0].id, selection[2].id]
    assert not _lock_of(selection[1]).exists()
    assert _record(changeset)['counts']['unchanged'] == 1


def test_reserved_series_is_listed(client, selection, any_approver):
    """A series that another change holds is left out and listed."""
    other = Changeset.objects.create(indexer=any_approver, state=states.OPEN,
                                     change_type=CTYPES['series'])
    _get_revision_lock(selection[1], other)

    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed']['reserved'] == [selection[1].id]
    assert 'Reserved: http' in changeset.comments.get().text
    assert changeset.seriesrevisions.count() == 2
    assert _lock_of(selection[1]).get().changeset == other


def test_deleted_series_is_invalid(client, selection):
    """A series deleted after the list was chosen is invalid."""
    Series.objects.filter(id=selection[1].id).update(deleted=True)

    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed']['invalid'] == [selection[1].id]
    assert 'It was deleted.' in changeset.comments.get().text
    assert changeset.seriesrevisions.count() == 2


def test_series_without_an_approved_revision_is_invalid(client, selection):
    """A series without an approved revision cannot be cloned."""
    SeriesRevision.objects.filter(series=selection[1]).delete()

    _apply(client)

    changeset = _change()
    assert _record(changeset)['listed']['invalid'] == [selection[1].id]
    assert 'It has no single approved revision.' in \
        changeset.comments.get().text
    assert not _lock_of(selection[1]).exists()


@pytest.mark.parametrize('values, message', [
    ({'year_ended': 1980}, 'Year ended cannot be before year began.'),
    ({'is_singleton': True, 'notes': 'Notes of its one issue.'},
     'Notes for singleton series are stored on the issue level.'),
], ids=['years out of order', 'singleton with notes'])
def test_series_that_already_fails_its_edit_form_is_blocked(client,
                                                            selection,
                                                            values, message):
    """A series that already fails its edit form is left out, blocked."""
    _approved(selection[1], **values)

    _apply(client)

    changeset = _change()
    record = _record(changeset)
    assert record['listed']['blocked'] == [selection[1].id]
    assert message in changeset.comments.get().text
    assert not changeset.seriesrevisions.filter(series=selection[1]).exists()
    assert not _lock_of(selection[1]).exists()
    assert record['counts']['changed'] == 2


def test_other_fields_keep_their_stored_values(client, selection,
                                               any_approver):
    """
    Only the field changes: a name that ends with a space, which its edit
    form would take off, keeps it, as stored, also after the approval.
    """
    _approved(selection[2], name='Series Three ')
    # The approval of that name made the sort name from it.
    Series.objects.filter(id=selection[2].id).update(sort_name='Series Three ')

    _apply(client)

    changeset = _change()
    assert _record(changeset)['counts']['changed'] == 3
    revision = changeset.seriesrevisions.get(series=selection[2])
    assert (revision.binding, revision.name) == \
        ('saddle-stitched', 'Series Three ')
    changeset.submit()
    changeset.assign(any_approver)
    changeset.approve()
    series = Series.objects.get(id=selection[2].id)
    assert (series.binding, series.name, series.sort_name) == \
        ('saddle-stitched', 'Series Three ', 'Series Three ')


def test_a_long_wait_on_the_publishers_has_words_of_its_own(client,
                                                            selection,
                                                            monkeypatch):
    """
    A wait beyond the server's limit on the rows that the series point to
    names their publishers, and nothing is changed.
    """
    def busy(*args):
        """Fail as a wait beyond the server's limit does."""
        raise OperationalError(bulk.LOCK_WAIT_TIMEOUT, 'from the test')
    monkeypatch.setattr(bulk, '_share_rows', busy)

    page = unescape(_apply(client).content.decode())

    assert WAIT_WORDS in page
    assert 'The series of these objects' not in page
    assert not Changeset.objects.filter(change_type=CTYPES['bulk']).exists()


def test_apply_holds_the_publishers_of_the_series(selection):
    """The rows that the new revisions point to are their publishers."""
    operation = bulk.Operation('binding', 'set', None, 'perfect bound')

    with CaptureQueriesContext(connection) as queries:
        bulk._hold_parents(Series, [one.id for one in selection], operation)

    held = [query['sql'] for query in queries if 'FOR SHARE' in query['sql']]
    assert [sql.split(' WHERE ')[0].split()[-1].strip('`') for sql in held] \
        == ['gcd_publisher']
    assert held[0].endswith('ORDER BY id FOR SHARE')
    assert str(selection[0].publisher_id) in held[0]


def test_submit_and_approval_write_the_values(client, selection,
                                              any_approver,
                                              reserving_indexer):
    """
    The change goes through the approval of any change, earns the point
    of one field, writes the values and frees every lock.
    """
    _apply(client)
    changeset = _change()
    imps = Indexer.objects.get(user=reserving_indexer).imps

    response = client.post(reverse('process', kwargs={'id': changeset.id}),
                           {'submit': 'Submit', 'comments': ''})

    assert response.status_code == 302
    changeset.refresh_from_db()
    assert changeset.state == states.PENDING
    assert changeset.imps == 1
    changeset.assign(any_approver)
    changeset.approve()
    assert changeset.state == states.APPROVED
    assert _values(selection) == ['saddle-stitched'] * 3
    assert not changeset.revision_locks.exists()
    assert not changeset.seriesrevisions.exclude(committed=True).exists()
    assert Indexer.objects.get(user=reserving_indexer).imps == imps + 1


def _untouched(series):
    """
    The values of series and of their publisher that a change of a
    format field must leave as they are, with the statistics rows and
    the ongoing reservations.
    """
    publisher = Publisher.objects.get(id=series[0].publisher_id)
    return (
      [(one.name, one.sort_name, one.issue_count, one.has_gallery,
        one.is_current, one.first_issue_id, one.last_issue_id)
       for one in Series.objects.filter(id__in=[one.id for one in series])
                                .order_by('id')],
      (publisher.series_count, publisher.issue_count),
      list(CountStats.objects.order_by('name', 'country', 'language', 'id')
           .values_list('name', 'country_id', 'language_id', 'count')),
      list(OngoingReservation.objects.values_list('series_id', 'indexer_id')))


def test_approval_leaves_what_the_fields_do_not_reach(make_change,
                                                      approve_change,
                                                      approved_series,
                                                      any_indexer):
    """
    The sort name with its leading article, the counts of the series and
    of their publisher, the statistics, the gallery flag and an ongoing
    reservation stay as they were.
    """
    first, second, third = approved_series
    _approved(first, is_current=True)
    OngoingReservation.objects.create(indexer=any_indexer, series=first)
    Series.objects.filter(id=second.id).update(has_gallery=True)
    Series.objects.filter(id=third.id).update(issue_count=7)
    CountStats.objects.init_stats()
    CountStats.objects.init_stats(country=first.country)
    CountStats.objects.init_stats(language=first.language)
    before = _untouched(approved_series)

    approve_change(make_change())

    assert _values(approved_series) == ['saddle-stitched'] * 3
    assert _untouched(approved_series) == before
    assert before[0][1][:2] == ('The Series Two', 'Series Two')
    assert ('series', None, None, 3) in before[2]


def test_change_history_lists_the_change_and_its_field(client, approved,
                                                       approved_series):
    """The history of a series names the bulk change and its field."""
    response = client.get(reverse('change_history', kwargs={
      'model_name': 'series', 'id': approved_series[0].id}))

    page = response.content.decode()
    assert _compare(approved) in page
    assert 'Binding' in page


def test_approval_locks_the_series_first(bulk_change, approved_series,
                                         any_approver):
    """
    The approval locks the rows of the series of the change, in id order,
    before it reads any of them, so that a count that another approval
    writes in the same moment is not put back.
    """
    changeset = bulk_change(approved_series, SeriesRevision,
                            binding='saddle-stitched')
    changeset.submit()
    changeset.assign(any_approver)

    with CaptureQueriesContext(connection) as queries:
        changeset.approve()

    touching = [query['sql'] for query in queries
                if '`gcd_series`' in query['sql']]
    assert touching[0].startswith('SELECT `gcd_series`.`id` AS `id` FROM')
    assert touching[0].endswith('ORDER BY 1 ASC FOR UPDATE')
    for one in approved_series:
        assert str(one.id) in touching[0]
    assert _values(approved_series) == ['saddle-stitched'] * 3


def test_edits_by_hand_are_refused(client, selection, any_approver):
    """
    No route changes a series revision of the change by hand, and no
    other indexer can reserve, move or delete a series that it holds.
    """
    _apply(client)
    changeset = _change()
    revision = changeset.seriesrevisions.get(series=selection[0])
    publisher_id = selection[0].publisher_id
    edited = {'model_name': 'series', 'id': revision.id}

    for method, url in (
          ('get', reverse('edit_revision', kwargs=edited)),
          ('post', reverse('process_revision', kwargs=edited)),
          ('get', reverse('move_series', kwargs={
            'series_revision_id': revision.id,
            'publisher_id': publisher_id}))):
        response = getattr(client, method)(url, {'save': 'Save'})
        assert REFUSED in response.content.decode(), url

    client.force_login(any_approver)
    held = {'model_name': 'series', 'id': selection[1].id}
    reserve = client.post(reverse('reserve_revision', kwargs=held),
                          follow=True)
    delete = client.post(reverse('delete_revision', kwargs=held),
                         {'comments': 'Gone.'}, follow=True)

    assert 'as it is reserved' in unescape(reserve.content.decode())
    assert 'fails the requirements for deletion' in \
        unescape(delete.content.decode())
    revision.refresh_from_db()
    assert revision.binding == 'saddle-stitched'
    assert not Series.objects.filter(id__in=[one.id for one in selection],
                                     deleted=True).exists()
    assert Changeset.objects.exclude(id=changeset.id).filter(
      state__in=states.ACTIVE).count() == 0
    assert _lock_of(selection[1]).get().changeset == changeset


def test_further_operation_on_another_field(client, make_change,
                                            approve_change):
    """
    An open change of series takes an operation on another of the five
    fields, whose page lists the values of its revisions; both fields
    reach the series at the approval.
    """
    changeset = make_change()

    listing = client.get(reverse('edit_issues_in_bulk'),
                         {'changeset': changeset.id, 'field': 'color'})
    response = _operate(client, changeset, COLOR)

    assert listing.context['form'].fields['old_value'].choices == [
      ('=four colors', '"four colors" (3)')]
    assert response.status_code == 302
    records = bulk.operation_records(changeset)
    assert [record['name'] for record in records] == ['binding', 'color']
    assert records[1]['counts']['changed'] == 3
    approve_change(changeset)
    assert changeset.imps == 2
    series = [revision.series for revision in changeset.seriesrevisions.all()]
    assert _values(series) == ['saddle-stitched'] * 3
    assert _values(series, 'color') == ['black and white'] * 3


def test_a_series_back_to_its_values_leaves(client, make_change,
                                            approved_series):
    """
    A revision that a further operation takes back to the values of its
    series leaves the change and frees the series; one that changes
    another field stays.
    """
    changeset = make_change()
    third = changeset.seriesrevisions.get(series=approved_series[2])
    SeriesRevision.objects.filter(id=third.id).update(color='two colors')

    response = _operate(client, changeset, BACK)

    assert response.status_code == 302
    assert [revision.id for revision in changeset.seriesrevisions.all()] == \
        [third.id]
    assert list(changeset.revision_locks.values_list('object_id',
                                                     flat=True)) == \
        [approved_series[2].id]
    records = bulk.operation_records(changeset)
    assert records[0]['counts']['removed'] == 2
    assert records[1]['counts']['removed'] == 2


def test_remove_selected_frees_the_series(client, make_change,
                                          approved_series):
    """Removal takes series out of the change and frees them."""
    changeset = make_change()
    first = changeset.seriesrevisions.get(series=approved_series[0])

    response = _remove(client, changeset, first.id)

    assert response['Location'] == _compare(changeset)
    assert changeset.seriesrevisions.count() == 2
    assert not _lock_of(approved_series[0]).exists()
    record = _record(changeset)
    assert (record['counts']['changed'], record['counts']['removed']) == \
        (2, 1)


def test_sweep_discards_a_change_of_series_left_alone(client, make_change,
                                                      any_approver,
                                                      approved_series):
    """An open change of series with no work for weeks is discarded."""
    changeset = make_change()
    _made_long_ago(changeset)

    _sweep(client, any_approver)

    changeset.refresh_from_db()
    assert changeset.state == states.DISCARDED
    assert not changeset.revision_locks.exists()
    assert _values(approved_series) == ['Saddle-stitched'] * 3


def test_revert_puts_the_values_back(client, approved, approved_series,
                                     approve_change):
    """
    A revert makes a new change that holds the old values; its approval
    puts them back on the series.
    """
    words = _show(client, approved)
    revert = _revert(client, approved)

    assert ('Restores the values from before change %d in all 3 of its '
            'series.' % approved.id) in words
    record = bulk.operation_record(revert)
    assert (record['model'], record['operation'], record['values']) == \
        ('series', 'restore', [approved.id])
    assert {revision.binding for revision in revert.seriesrevisions.all()} \
        == {'Saddle-stitched'}
    approve_change(revert)
    assert _values(approved_series) == ['Saddle-stitched'] * 3


def test_revert_leaves_out_a_value_changed_later(client, approved,
                                                 approved_series,
                                                 make_change, approve_change):
    """A series whose value changed since keeps it; the others go back."""
    approve_change(make_change(dict(BACK, new_value='perfect bound'),
                               approved_series[:1]))

    words = _show(client, approved)
    record = bulk.operation_record(_revert(client, approved))

    assert 'Changed later, so left out: 1' in words
    assert record['listed']['later'] == [approved_series[0].id]
    assert record['counts']['changed'] == 2


def test_revert_leaves_out_a_reserved_series(client, approved,
                                             approved_series, any_approver):
    """A series that another change holds is left out, and stays held."""
    other = Changeset.objects.create(indexer=any_approver, state=states.OPEN,
                                     change_type=CTYPES['series'])
    _get_revision_lock(approved_series[1], other)

    record = bulk.operation_record(_revert(client, approved))

    assert record['listed']['reserved'] == [approved_series[1].id]
    assert _lock_of(approved_series[1]).get().changeset == other


def test_revert_leaves_out_a_deleted_series(client, approved,
                                            approved_series):
    """A series deleted since the change is left out."""
    Series.objects.filter(id=approved_series[2].id).update(deleted=True)

    assert 'Deleted since that change, so left out: 1' in \
        _show(client, approved)
    record = bulk.operation_record(_revert(client, approved))

    assert record['listed']['deleted'] == [approved_series[2].id]
    assert record['counts']['changed'] == 2


def test_second_revert_is_refused(client, approved, approve_change):
    """A change reverted in full takes no second revert."""
    approve_change(_revert(client, approved))
    before = _counts()

    response = client.post(reverse('edit_issues_in_bulk') +
                           '?revert=%d' % approved.id)

    assert 'Nothing was changed, so no change was made' in _words(response)
    assert 'Reverted by change' in _words(client.get(_compare(approved)))
    assert 'Revert this bulk change' not in \
        _words(client.get(_compare(approved)))
    assert _counts() == before


def test_revert_drops_the_spaces_of_an_old_value(client, make_change,
                                                 approve_change,
                                                 approved_series):
    """Spaces that the edit form takes away do not come back."""
    _approved(approved_series[0], binding='Saddle-stitched ')
    changeset = make_change(dict(BINDING, old_value='=Saddle-stitched '),
                            approved_series[:1])
    approve_change(changeset)

    assert SPACES in _show(client, changeset)
    approve_change(_revert(client, changeset))

    assert _values(approved_series[:1]) == ['Saddle-stitched']
