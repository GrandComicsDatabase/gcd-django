"""The image upload page uses the upload card of the cover page."""

import io

import pytest
from PIL import Image as pyImage

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Image, ImageType
from apps.oi.forms.image import UploadImageForm
from apps.oi.models import ImageRevision

CARD = 'oi/bits/image_upload_card.html'
REPLACE_TEXTS = [
  'If you are replacing an image, please make sure that the image you '
  'upload is better than the one that is already there.',
  'Image replacements will usually be rejected unless they are '
  'significantly better, so do not expect your replacement image to always '
  'be accepted.',
]


@pytest.fixture
def media_root(tmp_path):
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


@pytest.fixture
def indicia_type():
    image_type, _ = ImageType.objects.get_or_create(
      name='IndiciaScan', defaults={'description': 'Indicia Scan'})
    return image_type


def _png(width=600, height=900):
    data = io.BytesIO()
    pyImage.new('RGB', (width, height), 'white').save(data, 'PNG')
    return data.getvalue()


def _upload_url(issue):
    return reverse('upload_image', kwargs={
      'model_name': 'issue', 'id': issue.id, 'image_type': 'IndiciaScan'})


@pytest.mark.django_db
def test_image_page_shows_upload_card(client, any_indexer, any_added_issue,
                                      indicia_type):
    client.force_login(any_indexer)

    response = client.get(_upload_url(any_added_issue))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-image-upload' in html
    assert 'name="image"' in html
    assert 'Upload an image' in html
    assert 'Upload Image</button>' in html
    assert ('href="%s"> Cancel</a>' % any_added_issue.get_absolute_url()
            in html)
    assert 'Mark image for replacement' in html
    assert 'please mark them for replacement.' in html
    # One button in the sticky bar, no table with a button above and below.
    assert 'value="Upload"' not in html
    # No pixel rule exists for these images.
    assert 'data-min-short-side' not in html
    assert 'too small' not in html


@pytest.mark.django_db
def test_cover_page_uses_shared_card(client, any_indexer, any_added_issue):
    client.force_login(any_indexer)

    response = client.get(reverse('upload_cover',
                                  kwargs={'issue_id': any_added_issue.id}))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-image-upload' in html
    assert 'data-min-short-side="400"' in html
    assert 'Upload a scan' in html
    assert 'At least 400 pixels on the short side' in html
    assert 'the shorter side must be at least 400 pixels' in html


def test_upload_card_texts():
    field = UploadImageForm()['image']

    html = render_to_string(CARD, {'field': field})

    assert 'data-image-upload' in html
    assert 'Upload an image' in html
    assert 'for="id_image"' in html
    assert 'name="image"' in html
    assert 'pixels on the short side' not in html
    assert 'data-upload="warning"' not in html
    assert 'data-min-short-side' not in html

    html = render_to_string(CARD, {'field': field, 'prompt': 'Upload a scan',
                                   'min_side': 400})

    assert 'Upload a scan' in html
    assert 'Upload an image' not in html
    assert 'At least 400 pixels on the short side' in html
    assert 'data-upload="warning"' in html
    assert 'the shorter side must be at least 400 pixels' in html
    assert 'data-min-short-side="400"' in html


@pytest.mark.django_db
def test_missing_file_shows_error_with_card(client, any_indexer,
                                            any_added_issue, indicia_type):
    client.force_login(any_indexer)

    response = client.post(_upload_url(any_added_issue),
                           {'comments': 'scanned myself'})

    assert response.status_code == 200
    html = response.content.decode()
    assert 'This field is required.' in html
    assert 'data-image-upload' in html
    assert ImageRevision.objects.count() == 0


@pytest.mark.django_db
def test_replace_page_shows_current_image(client, any_indexer,
                                          any_added_issue, indicia_type,
                                          media_root):
    image = Image.objects.create(
      content_type=ContentType.objects.get_for_model(any_added_issue),
      object_id=any_added_issue.id, type=indicia_type)
    image.image_file.save('indicia.png', ContentFile(_png()))
    replace_url = reverse('replace_image', kwargs={
      'model_name': 'issue', 'id': any_added_issue.id, 'image_id': image.id})
    client.force_login(any_indexer)

    response = client.get(replace_url)

    assert response.status_code == 200
    html = response.content.decode()
    assert 'Image to replace' in html
    assert 'action="%s"' % replace_url in html
    assert 'alt="current image"' in html
    for text in REPLACE_TEXTS:
        assert text in html


@pytest.mark.django_db
def test_upload_stores_image_revision(client, any_indexer, any_added_issue,
                                      indicia_type, media_root):
    client.force_login(any_indexer)

    response = client.post(_upload_url(any_added_issue), {
      'image': SimpleUploadedFile('indicia.png', _png(), 'image/png'),
      'marked': 'on',
      'comments': 'scanned myself'})

    assert response.status_code == 302
    assert response['Location'] == reverse('editing')
    revision = ImageRevision.objects.get()
    assert revision.type == indicia_type
    assert revision.object_id == any_added_issue.id
    assert revision.marked is True
