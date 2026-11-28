import json
import tempfile

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.oi.models import CTYPES, IssueRevision, StoryRevision

GOOD_SEQUENCE = {'type': 'comic story', 'title': 'Good', 'page_count': '1'}
BAD_SEQUENCE = {'type': 'no such type', 'title': 'Bad', 'page_count': '1'}
GOOD_LINE = b'1,,,,January 2000,2000-01-00,,1.00 USD,32,None\n'
BAD_LINE = b'2,,,,February 2000,not a date,,1.00 USD,32,None\n'


@pytest.fixture
def revision(client, any_indexer, any_added_issue, any_editing_changeset):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    # Issues added to a series without printers are a separate problem.
    series = any_added_issue.series
    series.has_indicia_printer = True
    series.save()
    any_editing_changeset.change_type = CTYPES['issue']
    any_editing_changeset.save()
    return IssueRevision.clone(data_object=any_added_issue,
                               changeset=any_editing_changeset)


def _upload_to_revision(client, url_name, revision, content):
    return client.post(
      reverse(url_name, kwargs={'issue_id': revision.issue_id,
                                'changeset_id': revision.changeset_id}),
      {'flatfile': SimpleUploadedFile('upload', json.dumps(content).encode()),
       'json': '1'})


def _upload_to_series(client, series, content, **options):
    return client.post(
      reverse('import_issues_to_series', kwargs={'series_id': series.id}),
      {'file': SimpleUploadedFile('upload', content), **options})


def _error_page(client, response):
    return client.get(response.url).content.decode()


def _issues_added_to(series):
    return IssueRevision.objects.filter(series=series, issue__isnull=True)


@pytest.mark.django_db
def test_a_failed_sequence_upload_saves_nothing(client, revision):
    response = _upload_to_revision(client, 'import_stories', revision, {
      'story_set': [GOOD_SEQUENCE, BAD_SEQUENCE]})

    assert 'does not exist.' in _error_page(client, response)
    assert not StoryRevision.objects.filter(
      changeset=revision.changeset).exists()


@pytest.mark.django_db
def test_a_failed_issue_upload_leaves_the_issue_as_it_was(client, revision):
    number = revision.number

    response = _upload_to_revision(client, 'import_issue', revision, {
      'number': number + '9', 'story_set': [GOOD_SEQUENCE, BAD_SEQUENCE]})

    assert 'does not exist.' in _error_page(client, response)
    assert IssueRevision.objects.get(pk=revision.pk).number == number
    assert not StoryRevision.objects.filter(
      changeset=revision.changeset).exists()


@pytest.mark.django_db
def test_a_failed_series_upload_adds_no_issue(client, revision):
    response = _upload_to_series(client, revision.series,
                                 GOOD_LINE + BAD_LINE)

    assert 'is invalid.' in _error_page(client, response)
    assert not _issues_added_to(revision.series).exists()


@pytest.mark.django_db
def test_a_good_series_upload_adds_its_issues(client, revision):
    _upload_to_series(client, revision.series, GOOD_LINE)

    assert _issues_added_to(revision.series).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('story_set', ([GOOD_SEQUENCE], [BAD_SEQUENCE]))
def test_a_sequence_upload_leaves_no_temporary_file(
  client, revision, monkeypatch, tmp_path, story_set):
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))

    _upload_to_revision(client, 'import_stories', revision,
                        {'story_set': story_set})

    assert list(tmp_path.glob('*.import')) == []


@pytest.mark.django_db
@pytest.mark.parametrize(('content', 'options'), (
    (GOOD_LINE, {}),
    (BAD_LINE, {}),
    (json.dumps({'issue_set': []}).encode(), {'json': '1'}),
))
def test_a_series_upload_leaves_no_temporary_file(
  client, revision, monkeypatch, tmp_path, content, options):
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))

    _upload_to_series(client, revision.series, content, **options)

    assert list(tmp_path.glob('*.import')) == []
