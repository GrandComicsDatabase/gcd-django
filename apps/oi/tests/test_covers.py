import io
import os

import pytest
from PIL import Image as pyImage

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.oi.models import Changeset, CoverRevision


@pytest.fixture
def media_root(tmp_path):
    os.makedirs(tmp_path / 'img' / 'gcd' / 'new_covers' / 'tmp')
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        yield tmp_path


@pytest.fixture
def tmp_dir(media_root):
    return media_root / 'img' / 'gcd' / 'new_covers' / 'tmp'


@pytest.fixture
def outside_file(media_root):
    outside = media_root / 'outside.jpg'
    outside.write_bytes(b'not to be touched')
    return outside


def _gatefold_data(issue, scan_name, **kwargs):
    data = {'left': 0, 'width': 500, 'real_width': 1000, 'top': 0,
            'height': 600, 'issue_id': issue.id, 'scan_name': scan_name,
            'source': 'scanned myself', 'comments': ''}
    data.update(kwargs)
    return data


@pytest.mark.django_db
def test_gatefold_requires_login(client, any_added_issue, outside_file):
    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue, '../../../../outside.jpg',
                     discard='Discard'))

    assert response.status_code == 302
    assert reverse('login') in response['Location']
    assert outside_file.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('scan_name', [
  '../../../../outside.jpg',
  '{media_root}/outside.jpg',
])
def test_gatefold_rejects_path_outside_tmp_dir(
  client, any_indexer, any_added_issue, media_root, outside_file, scan_name):
    client.force_login(any_indexer)

    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue,
                     scan_name.format(media_root=media_root),
                     discard='Discard'))

    assert response.status_code == 200
    assert outside_file.exists()


@pytest.mark.django_db
def test_gatefold_rejects_scan_of_other_user(
  client, any_indexer, any_added_issue, tmp_dir):
    other_scan = tmp_dir / ('%d_%d.jpg' % (any_indexer.id + 1,
                                           any_added_issue.id))
    other_scan.write_bytes(b'upload of another user')
    client.force_login(any_indexer)

    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue, other_scan.name, discard='Discard'))

    assert response.status_code == 200
    assert other_scan.exists()


@pytest.mark.django_db
def test_gatefold_discard_removes_own_scan(
  client, any_indexer, any_added_issue, tmp_dir):
    own_scan = tmp_dir / ('%d_%d.jpg' % (any_indexer.id, any_added_issue.id))
    own_scan.write_bytes(b'own upload')
    client.force_login(any_indexer)

    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue, own_scan.name, discard='Discard'))

    assert response.status_code == 302
    assert not own_scan.exists()


def _write_scan(tmp_dir, user, issue):
    scan = tmp_dir / ('%d_%d.jpg' % (user.id, issue.id))
    pyImage.new('RGB', (1000, 600), 'white').save(scan)
    return scan


@pytest.mark.django_db
def test_gatefold_keeps_selection_inside_scan(
  client, any_indexer, any_added_issue, tmp_dir):
    scan = _write_scan(tmp_dir, any_indexer, any_added_issue)
    client.force_login(any_indexer)

    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue, scan.name, left=501, width=500,
                     top=-1, height=602))

    assert response.status_code == 302
    revision = CoverRevision.objects.get(issue=any_added_issue)
    assert (revision.front_left, revision.front_right,
            revision.front_top, revision.front_bottom) == (501, 1000, 0, 600)
    assert not scan.exists()


@pytest.mark.django_db
def test_gatefold_upload_and_selection(client, any_indexer, any_added_issue,
                                       media_root):
    scan = io.BytesIO()
    pyImage.new('RGB', (1000, 600), 'white').save(scan, 'JPEG')
    client.force_login(any_indexer)

    response = client.post(
      reverse('upload_cover', kwargs={'issue_id': any_added_issue.id}),
      {'scan': SimpleUploadedFile('gatefold.jpg', scan.getvalue()),
       'source': 'scanned myself', 'is_gatefold': 'on', 'comments': ''})

    assert response.status_code == 200
    scan_name = response.context['form'].initial['scan_name']
    assert scan_name == '%d_%d.jpg' % (any_indexer.id, any_added_issue.id)

    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue, scan_name, left=500))

    assert response.status_code == 302
    revision = CoverRevision.objects.get(issue=any_added_issue)
    assert (revision.front_left, revision.front_right) == (500, 1000)


@pytest.mark.django_db
@pytest.mark.parametrize('selection', [
  {'left': 0, 'width': 1},
  {'left': 0, 'width': 0},
  {'left': 990, 'width': 500},
  {'top': 0, 'height': 1},
])
def test_gatefold_rejects_too_small_front_part(
  client, any_indexer, any_added_issue, tmp_dir, selection):
    scan = _write_scan(tmp_dir, any_indexer, any_added_issue)
    client.force_login(any_indexer)
    changesets = Changeset.objects.count()

    response = client.post(
      reverse('gatefold_cover'),
      _gatefold_data(any_added_issue, scan.name, **selection))

    assert response.status_code == 200
    assert Changeset.objects.count() == changesets
    assert scan.exists()
