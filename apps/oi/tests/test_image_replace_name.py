"""A replaced image gets a new file name, so that its address changes."""

import io
import os

import pytest
from PIL import Image as pyImage

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Image, ImageType
from apps.oi import states
from apps.oi.models import Changeset


@pytest.fixture
def media_root(tmp_path):
    """Keep the uploaded files and their copies in a temporary folder."""
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


@pytest.fixture
def indicia_type():
    """The type of the uploaded images."""
    image_type, _ = ImageType.objects.get_or_create(
      name='IndiciaScan', defaults={'description': 'Indicia Scan'})
    return image_type


def _scan(color):
    """A JPEG upload of one color."""
    data = io.BytesIO()
    pyImage.new('RGB', (600, 900), color).save(data, 'JPEG')
    return SimpleUploadedFile('scan.jpg', data.getvalue(), 'image/jpeg')


def _upload(client, url, color):
    """Upload a scan and approve the change; return its revision."""
    response = client.post(url, {'image': _scan(color),
                                 'comments': 'scanned myself'})
    assert response.status_code == 302
    changeset = Changeset.objects.latest('id')
    changeset.approver = changeset.indexer
    changeset.state = states.REVIEWING
    changeset.save()
    changeset.approve()
    return changeset.imagerevisions.get()


def _copies(image):
    """The files of the scaled copies, made as a page would make them."""
    return [image.scaled_image.path, image.thumbnail.path, image.icon.path]


@pytest.mark.django_db
def test_replaced_image_gets_new_name(client, any_indexer, any_added_issue,
                                      indicia_type, media_root):
    """
    After the approval of a replacement the image and its scaled copies
    have new names, the page shows them at new addresses, the copies of
    the old file are gone and the old file stays with the revision before.
    """
    client.force_login(any_indexer)
    _upload(client, reverse('upload_image', kwargs={
      'model_name': 'issue', 'id': any_added_issue.id,
      'image_type': 'IndiciaScan'}), 'white')
    image = Image.objects.get()
    old_name = image.image_file.name
    old_urls = [image.image_file.url, image.scaled_image.url]
    with image.image_file.open('rb') as old_file:
        old_content = old_file.read()
    old_copies = _copies(image)
    assert all(os.path.exists(path) for path in old_copies)

    revision = _upload(client, reverse('replace_image', kwargs={
      'model_name': 'issue', 'id': any_added_issue.id,
      'image_id': image.id}), 'black')

    # A first upload keeps the name it always had.
    assert old_name.endswith('/%d.jpg' % image.id)
    assert not any(os.path.exists(path) for path in old_copies)
    image = Image.objects.get()
    assert image.image_file.name.endswith(
      '/%d_%d.jpg' % (image.id, revision.id))
    new_urls = [image.image_file.url, image.scaled_image.url]
    assert not set(_copies(image)) & set(old_copies)
    page = client.get(reverse('issue_images', kwargs={
      'issue_id': any_added_issue.id})).content.decode()
    assert all(url in page for url in new_urls)
    assert not any(url in page for url in old_urls)
    # The replaced file stays with the revision before, as it did.
    with revision.previous().image_file.open('rb') as kept_file:
        assert kept_file.read() == old_content
