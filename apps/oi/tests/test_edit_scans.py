"""The edit page of an issue or a sequence shows the scan to copy from."""

import io

import pytest
from PIL import Image as pyImage

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Image, ImageType, StoryType
from apps.gcd.models.story import STORY_TYPES
from apps.oi.models import CTYPES, IssueRevision

INDICIA = 'Indicia Scan</summary>'
SOO = 'Statement of Ownership Scan</summary>'


@pytest.fixture
def media_root(tmp_path):
    """Store the scans of the test in a folder of its own."""
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


@pytest.fixture
def indexer_client(client, any_indexer):
    """A client logged in as an indexer who can edit."""
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


def _add_scan(issue, type_name):
    """Give the issue a scan of the named image type."""
    image = Image.objects.create(
      content_type=ContentType.objects.get_for_model(issue),
      object_id=issue.id, type=ImageType.objects.get(name=type_name))
    data = io.BytesIO()
    pyImage.new('RGB', (600, 900), 'white').save(data, 'PNG')
    image.image_file.save('scan.png', ContentFile(data.getvalue()))
    return image


def _edit_page(client, revision, model_name):
    """The html of the edit page of the revision."""
    response = client.get(reverse('edit_revision', kwargs={
      'model_name': model_name, 'id': revision.id}))
    assert response.status_code == 200
    return response.content.decode()


def _issue_revision(issue, changeset):
    """An edit of the issue, in a change of the issue."""
    changeset.change_type = CTYPES['issue']
    changeset.save()
    return IssueRevision.clone(data_object=issue, changeset=changeset)


def _story_revision(revision, type_name):
    """The edit of the sequence, as a sequence of the given type."""
    changeset = revision.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    revision.type = StoryType.objects.get(id=STORY_TYPES[type_name])
    revision.save()
    return revision


@pytest.mark.django_db
def test_issue_edit_shows_indicia_scan(indexer_client, any_added_issue,
                                       any_editing_changeset, media_root):
    image = _add_scan(any_added_issue, 'IndiciaScan')
    revision = _issue_revision(any_added_issue, any_editing_changeset)

    html = _edit_page(indexer_client, revision, 'issue')

    assert INDICIA in html
    assert 'src="%s"' % image.scaled_image_url in html
    assert ('href="%s" target="_blank"' % image.image_file_url) in html
    assert 'Open in a new window' in html
    assert SOO not in html


@pytest.mark.django_db
def test_issue_edit_without_indicia_scan_shows_none(
        indexer_client, any_added_issue, any_editing_changeset, media_root):
    # a scan of the statement of ownership is for its sequence only
    _add_scan(any_added_issue, 'SoOScan')
    revision = _issue_revision(any_added_issue, any_editing_changeset)

    html = _edit_page(indexer_client, revision, 'issue')

    assert INDICIA not in html
    assert SOO not in html


@pytest.mark.django_db
def test_new_issue_shows_no_scan(indexer_client, any_added_issue_rev):
    changeset = any_added_issue_rev.changeset
    changeset.change_type = CTYPES['issue_add']
    changeset.save()

    html = _edit_page(indexer_client, any_added_issue_rev, 'issue')

    assert any_added_issue_rev.issue is None
    assert INDICIA not in html


@pytest.mark.django_db
def test_soo_sequence_shows_soo_scan(indexer_client, any_edit_story_rev,
                                     media_root):
    revision = _story_revision(any_edit_story_rev, 'soo')
    image = _add_scan(revision.issue, 'SoOScan')
    _add_scan(revision.issue, 'IndiciaScan')

    html = _edit_page(indexer_client, revision, 'story')

    assert SOO in html
    assert 'src="%s"' % image.scaled_image_url in html
    assert ('href="%s" target="_blank"' % image.image_file_url) in html
    assert INDICIA not in html


@pytest.mark.django_db
def test_soo_sequence_without_scan_shows_none(indexer_client,
                                              any_edit_story_rev):
    revision = _story_revision(any_edit_story_rev, 'soo')

    html = _edit_page(indexer_client, revision, 'story')

    assert SOO not in html


@pytest.mark.django_db
def test_other_sequence_shows_no_scan(indexer_client, any_edit_story_rev,
                                      media_root):
    revision = _story_revision(any_edit_story_rev, 'comic story')
    _add_scan(revision.issue, 'SoOScan')
    _add_scan(revision.issue, 'IndiciaScan')

    html = _edit_page(indexer_client, revision, 'story')

    assert SOO not in html
    assert INDICIA not in html
