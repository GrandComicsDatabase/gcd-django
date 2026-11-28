import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from apps.gcd.models import Series
from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.forms import get_revision_form
from apps.oi.models import Changeset, CTYPES, SeriesRevision

KEYWORDS_ERROR = ('Keywords for singleton series are stored on the issue '
                  'level.')


@pytest.fixture
def indexer_client(client, any_indexer):
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


@pytest.fixture
def approver(any_country):
    user = User.objects.create_user('approver', password='approver')
    Indexer.objects.create(user=user, country=any_country)
    return user


@pytest.fixture
def series_changeset(any_indexer):
    return Changeset.objects.create(state=states.OPEN, indexer=any_indexer,
                                    change_type=CTYPES['series'])


def _as_singleton(revision):
    revision.is_singleton = True
    revision.is_current = False
    revision.has_issue_title = False
    revision.save()
    return revision


def _approved_singleton(revision, approver):
    """ Runs the real approval of a new singleton series. """
    _as_singleton(revision)
    changeset = revision.changeset
    changeset.change_type = CTYPES['series']
    changeset.state = states.REVIEWING
    changeset.approver = approver
    changeset.save()
    changeset.approve()
    return SeriesRevision.objects.get(pk=revision.pk)


def _old_singleton(series, changeset):
    """ An edit of a singleton whose keywords are still on the series. """
    Series.objects.filter(pk=series.pk).update(
      is_singleton=True, is_current=False, has_issue_title=False, notes='')
    return SeriesRevision.clone(data_object=Series.objects.get(pk=series.pk),
                                changeset=changeset)


def _post_edit_form(client, revision, **changes):
    """ Posts the series form as its edit page fills it in. """
    user = revision.changeset.indexer
    form = get_revision_form(revision, user=user)(instance=revision)
    data = {field.html_name: field.value() for field in form
            if field.value() not in (None, False)}
    formset = revision.extra_forms(
      RequestFactory().get('/'))['external_link_formset']
    data['%s-TOTAL_FORMS' % formset.prefix] = '0'
    data['%s-INITIAL_FORMS' % formset.prefix] = '0'
    data['save'] = 'Save'
    data.update(changes)
    return client.post(reverse('process_revision',
                               kwargs={'model_name': 'series',
                                       'id': revision.id}), data)


@pytest.mark.django_db
@pytest.mark.parametrize('notes', ['blah blah whatever', ''])
def test_new_singleton_has_its_keywords_on_the_issue_only(
  any_added_series_rev, approver, keywords, notes):
    any_added_series_rev.notes = notes

    revision = _approved_singleton(any_added_series_rev, approver)

    issue = revision.series.active_issues().get()
    assert sorted(k.name for k in issue.keywords.all()) == keywords['list']
    assert issue.notes == notes
    assert revision.keywords == ''
    assert not revision.series.keywords.exists()
    assert revision.series.notes == ''


@pytest.mark.django_db
def test_new_singleton_can_be_edited_and_saved(
  indexer_client, any_added_series_rev, approver, series_changeset):
    revision = _approved_singleton(any_added_series_rev, approver)
    edit = SeriesRevision.clone(data_object=revision.series,
                                changeset=series_changeset)

    response = _post_edit_form(indexer_client, edit)

    assert response.status_code == 302


@pytest.mark.django_db
def test_old_singleton_can_be_edited_with_its_stored_keywords(
  indexer_client, any_added_series, series_changeset):
    edit = _old_singleton(any_added_series, series_changeset)
    assert edit.keywords

    response = _post_edit_form(indexer_client, edit, name='Changed Name')

    assert response.status_code == 302
    edit = SeriesRevision.objects.get(pk=edit.pk)
    assert edit.name == 'Changed Name'
    assert edit.keywords


@pytest.mark.django_db
def test_changing_the_keywords_of_old_singleton_is_refused(
  indexer_client, any_added_series, series_changeset):
    edit = _old_singleton(any_added_series, series_changeset)

    response = _post_edit_form(indexer_client, edit, keywords='other')

    assert response.status_code == 200
    assert KEYWORDS_ERROR in response.content.decode()


@pytest.mark.django_db
def test_series_with_keywords_cannot_become_singleton(
  indexer_client, any_added_series, series_changeset):
    edit = SeriesRevision.clone(data_object=any_added_series,
                                changeset=series_changeset)
    assert edit.keywords

    response = _post_edit_form(indexer_client, edit, is_singleton='on',
                               is_current='', has_issue_title='', notes='')

    assert response.status_code == 200
    assert KEYWORDS_ERROR in response.content.decode()


@pytest.mark.django_db
def test_edit_of_old_singleton_saves_once_keywords_are_removed(
  indexer_client, any_added_series, series_changeset):
    edit = _old_singleton(any_added_series, series_changeset)

    response = _post_edit_form(indexer_client, edit, keywords='')

    assert response.status_code == 302
    assert SeriesRevision.objects.get(pk=edit.pk).keywords == ''


@pytest.mark.django_db
def test_bad_keyword_on_singleton_is_a_form_error(
  indexer_client, any_added_series, series_changeset):
    edit = _old_singleton(any_added_series, series_changeset)

    response = _post_edit_form(indexer_client, edit, keywords='foo; <bar>')

    assert response.status_code == 200
    assert 'not allowed in a keyword' in response.content.decode()


@pytest.mark.django_db
def test_added_singleton_keeps_keywords_until_approved(
  indexer_client, any_added_series_rev):
    _as_singleton(any_added_series_rev)

    response = _post_edit_form(indexer_client, any_added_series_rev)

    assert response.status_code == 302
    assert SeriesRevision.objects.get(
      pk=any_added_series_rev.pk).keywords != ''


@pytest.mark.django_db
def test_ordinary_series_keeps_keywords(
  indexer_client, any_added_series, series_changeset):
    edit = SeriesRevision.clone(data_object=any_added_series,
                                changeset=series_changeset)

    response = _post_edit_form(indexer_client, edit)

    assert response.status_code == 302
