"""A replaced image keeps its file name and gets a new version in its
addresses, so that no cache keeps showing the old picture."""

import io

import pytest
from PIL import Image as pyImage

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Creator, CreatorSignature, Image, ImageType
from apps.oi import states
from apps.oi.models import Changeset
from apps.stddata.models import Date


@pytest.fixture
def media_root(tmp_path):
    """Keep the uploaded files and their copies in a temporary folder."""
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


def _jpeg(color):
    """The bytes of a JPEG of one color."""
    data = io.BytesIO()
    pyImage.new('RGB', (600, 900), color).save(data, 'JPEG')
    return data.getvalue()


def _upload(client, url, color):
    """Upload a scan and approve the change; return its revision."""
    response = client.post(url, {
      'image': SimpleUploadedFile('scan.jpg', _jpeg(color), 'image/jpeg'),
      'comments': 'scanned myself'})
    assert response.status_code == 302
    changeset = Changeset.objects.latest('id')
    changeset.approver = changeset.indexer
    changeset.state = states.REVIEWING
    changeset.save()
    changeset.approve()
    return changeset.imagerevisions.get()


def _versioned(image, url):
    """The address with the version the pages give it."""
    return '%s?%d' % (url, hash(image.modified))


@pytest.mark.django_db
def test_replaced_image_keeps_its_name_and_gets_a_new_version(
      client, any_indexer, any_added_issue, media_root):
    """
    After the approval of a replacement the file keeps its name, the
    scaled copy shows the new picture, and the issue's image page gives
    the file and its scaled copy a new version in their addresses.
    """
    ImageType.objects.get_or_create(
      name='IndiciaScan', defaults={'description': 'Indicia Scan'})
    client.force_login(any_indexer)
    _upload(client, reverse('upload_image', kwargs={
      'model_name': 'issue', 'id': any_added_issue.id,
      'image_type': 'IndiciaScan'}), 'white')
    image = Image.objects.get()
    old_name = image.image_file.name
    old_urls = [_versioned(image, image.image_file.url),
                _versioned(image, image.scaled_image.url)]

    _upload(client, reverse('replace_image', kwargs={
      'model_name': 'issue', 'id': any_added_issue.id,
      'image_id': image.id}), 'black')

    image = Image.objects.get()
    assert image.image_file.name == old_name
    with pyImage.open(image.scaled_image.path) as scaled:
        assert scaled.convert('L').getpixel((10, 10)) < 50
    new_urls = [_versioned(image, image.image_file.url),
                _versioned(image, image.scaled_image.url)]
    assert not set(new_urls) & set(old_urls)
    page = client.get(reverse('issue_images', kwargs={
      'issue_id': any_added_issue.id})).content.decode()
    assert all(url in page for url in new_urls)
    assert not any(url in page for url in old_urls)


@pytest.mark.django_db
def test_signature_page_gives_the_image_its_version(client, media_root):
    """The signature page shows the scaled image with its version."""
    signature_type, _ = ImageType.objects.get_or_create(
      id=7, defaults={'name': 'CreatorSignature',
                      'description': 'signature scan'})
    creator = Creator.objects.create(
      gcd_official_name='Test Creator', sort_name='Creator, Test',
      birth_date=Date.objects.create(year='1950'))
    creator_signature = CreatorSignature.objects.create(
      name='Test Creator', creator=creator, notes='')
    image = Image.objects.create(
      content_type=ContentType.objects.get_for_model(CreatorSignature),
      object_id=creator_signature.id, type=signature_type)
    image.image_file.save('%d.jpg' % image.id, ContentFile(_jpeg('blue')))

    page = client.get(creator_signature.get_absolute_url()).content.decode()

    assert _versioned(image, image.scaled_image.url) in page
