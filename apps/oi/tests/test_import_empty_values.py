import json

import pytest
import yaml
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.oi.models import CTYPES, IssueRevision, StoryRevision

FORMATS = (('json', json.dumps), ('yaml', yaml.safe_dump))


@pytest.fixture
def revision(client, any_indexer, any_added_issue, any_editing_changeset):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    any_editing_changeset.change_type = CTYPES['issue']
    any_editing_changeset.save()
    return IssueRevision.clone(data_object=any_added_issue,
                               changeset=any_editing_changeset)


def _upload(client, url_name, revision, file_format, content):
    return client.post(
      reverse(url_name, kwargs={'issue_id': revision.issue_id,
                                'changeset_id': revision.changeset_id}),
      {'flatfile': SimpleUploadedFile('upload', content.encode()),
       file_format: '1'})


def _error_page(client, response):
    return client.get(response.url).content.decode()


def _imported_stories(revision):
    return StoryRevision.objects.filter(changeset=revision.changeset)


@pytest.mark.django_db
@pytest.mark.parametrize(('file_format', 'dump'), FORMATS)
def test_a_sequence_with_null_values_is_imported(client, revision,
                                                 file_format, dump):
    _upload(client, 'import_stories', revision, file_format, dump({
      'story_set': [{'type': 'comic story', 'title': None, 'page_count': None,
                     'script': None, 'notes': None}]}))

    story = _imported_stories(revision).get()
    assert story.title == ''
    assert story.script == ''
    assert story.notes == ''
    assert story.page_count is None


@pytest.mark.django_db
@pytest.mark.parametrize(('file_format', 'dump'), FORMATS)
def test_a_sequence_without_a_page_count_is_imported(client, revision,
                                                     file_format, dump):
    _upload(client, 'import_stories', revision, file_format, dump({
      'story_set': [{'type': 'comic story', 'title': 'A Title'}]}))

    story = _imported_stories(revision).get()
    assert story.title == 'A Title'
    assert story.page_count is None


@pytest.mark.django_db
@pytest.mark.parametrize('sequence', ({'title': 'A Title'},
                                      {'title': 'A Title', 'type': None},
                                      {'title': 'A Title', 'type': 'no type'}))
def test_a_sequence_without_a_valid_type_gets_the_error_page(client, revision,
                                                             sequence):
    response = _upload(client, 'import_stories', revision, 'json', json.dumps(
      {'story_set': [sequence]}))

    page = _error_page(client, response)
    assert 'does not exist.' in page
    assert 'href="%s"' % reverse('edit', kwargs={'id': revision.changeset_id}
                                 ) in page
    assert not _imported_stories(revision).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(('file_format', 'dump'), FORMATS)
def test_an_issue_with_null_values_is_imported(client, revision, file_format,
                                               dump):
    _upload(client, 'import_issue', revision, file_format, dump({
      'number': '7', 'notes': None, 'price': None, 'editing': None,
      'brand_emblem': None, 'indicia_publisher': None, 'key_date': None,
      'page_count': None, 'publication_date': None, 'story_set': []}))

    revision = IssueRevision.objects.get(pk=revision.pk)
    assert revision.number == '7'
    assert revision.notes == ''
    assert revision.price == ''


@pytest.mark.django_db
@pytest.mark.parametrize('content', ({'number': '7'},
                                     {'number': '7', 'story_set': None}))
def test_an_issue_without_sequences_is_imported(client, revision, content):
    _upload(client, 'import_issue', revision, 'json', json.dumps(content))

    assert IssueRevision.objects.get(pk=revision.pk).number == '7'
    assert not _imported_stories(revision).exists()


@pytest.mark.django_db
def test_a_variant_cover_without_a_type_gets_the_error_page(client, revision):
    series = revision.series
    # Issues added to a series without printers are a separate problem.
    series.has_indicia_printer = True
    series.save()
    upload = SimpleUploadedFile('upload', json.dumps({'issue_set': [{
      'number': revision.issue.number, 'variant_name': 'A Variant',
      'variant_cover_status': 'ARTWORK_DIFFERENCE',
      'story_set': [{'type': None}]}]}).encode())

    response = client.post(reverse('import_issues_to_series',
                                   kwargs={'series_id': series.id}),
                           {'file': upload, 'json': '1'})

    assert 'is not of type cover.' in _error_page(client, response)


@pytest.mark.django_db
@pytest.mark.parametrize('content', ({}, {'story_set': None}))
def test_a_file_without_sequences_adds_nothing(client, revision, content):
    response = _upload(client, 'import_stories', revision, 'json',
                       json.dumps(content))

    assert response.url == reverse('edit',
                                   kwargs={'id': revision.changeset_id})
    assert not _imported_stories(revision).exists()
