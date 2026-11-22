"""The compare page of a creator signature shows the other signatures."""
import io

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.template import Context, Template
from django.urls import reverse
from PIL import Image as PillowImage

from apps.gcd.models import Creator, CreatorSignature, Image, ImageType
from apps.oi import states
from apps.oi.models import (
    CTYPES, Changeset, CreatorSignatureRevision, ImageRevision)
from apps.stddata.models import Date

pytestmark = pytest.mark.django_db


def _jpeg():
    """Return a small image file."""
    data = io.BytesIO()
    PillowImage.new('RGB', (60, 20), 'white').save(data, 'JPEG')
    return ContentFile(data.getvalue())


def _creator(name):
    return Creator.objects.create(
      gcd_official_name=name, birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='',
      birth_date=Date.objects.create())


def _signature(creator, name, **values):
    return CreatorSignature.objects.create(creator=creator, name=name,
                                           notes='', **values)


def _image(model, signature, **values):
    """Upload an image for a signature or a signature revision."""
    image = model.objects.create(
      type=ImageType.objects.get(name='CreatorSignature'),
      content_type=ContentType.objects.get_for_model(signature),
      object_id=signature.id, **values)
    image.image_file.save('%d.jpg' % image.id, _jpeg())
    return image


@pytest.fixture
def creator():
    return _creator('Some Creator')


@pytest.fixture
def real_images(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.FAKE_IMAGES = False


def _added_signature(indexer, creator, **values):
    changeset = Changeset.objects.create(
      indexer=indexer, state=states.OPEN,
      change_type=CTYPES['creator_signature'])
    return CreatorSignatureRevision.objects.create(
      changeset=changeset, creator=creator, name='New Name', **values)


def _compare_page(client, indexer, revision):
    client.force_login(indexer)
    return client.get(reverse('compare', kwargs={
      'id': revision.changeset_id})).content.decode()


def test_generic_signature_compare_lists_the_others(client, any_indexer,
                                                    creator):
    old = _signature(creator, 'Old Name')
    _signature(creator, 'Gone Name', deleted=True)
    _signature(_creator('Another Creator'), 'Foreign Name')
    revision = _added_signature(any_indexer, creator, generic=True)

    page = _compare_page(client, any_indexer, revision)

    assert 'Other signatures of this creator' in page
    assert '<a href="%s">Old Name</a>' % old.get_absolute_url() in page
    assert 'Gone Name' not in page
    assert 'Foreign Name' not in page


def test_image_signature_compare_shows_the_images(client, any_indexer,
                                                  creator, real_images):
    image = _image(Image, _signature(creator, 'Old Name'))
    revision = _added_signature(any_indexer, creator)
    revision.image_revision = _image(ImageRevision, revision,
                                     changeset=revision.changeset)
    revision.save()

    page = _compare_page(client, any_indexer, revision)

    assert 'Other signatures of this creator' in page
    assert image.thumbnail.url in page


def test_other_signatures_without_a_query_per_signature(
      django_assert_num_queries, creator, real_images):
    edited = _signature(creator, 'Edited Name')
    images = [_image(Image, _signature(creator, 'Name %d' % number))
              for number in range(3)]
    _signature(creator, 'Plain Name', generic=True)
    revision = CreatorSignatureRevision(creator=creator, name='Edited Name',
                                        creator_signature=edited)
    template = Template('{% load compare %}{% other_signatures revision %}')

    with django_assert_num_queries(2):
        html = template.render(Context({'revision': revision}))

    for image in images:
        assert image.thumbnail.url in html
    assert 'Plain Name</a> [generic]' in html
    assert 'Edited Name' not in html


def test_no_list_for_other_changes(any_added_publisher_rev):
    template = Template('{% load compare %}{% other_signatures revision %}')
    html = template.render(Context({'revision': any_added_publisher_rev}))
    assert html == ''
