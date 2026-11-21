"""A replacement sent without a valid file stays on the replace page."""

import io

import pytest
from PIL import Image as pyImage

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Image, ImageType
from apps.oi.models import ImageRevision


@pytest.fixture
def media_root(tmp_path):
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


@pytest.fixture
def indicia_image(any_added_issue, media_root):
    image_type, _ = ImageType.objects.get_or_create(
      name='IndiciaScan', defaults={'description': 'Indicia Scan'})
    image = Image.objects.create(
      content_type=ContentType.objects.get_for_model(any_added_issue),
      object_id=any_added_issue.id, type=image_type)
    data = io.BytesIO()
    pyImage.new('RGB', (600, 900), 'white').save(data, 'PNG')
    image.image_file.save('indicia.png', ContentFile(data.getvalue()))
    return image


@pytest.mark.django_db
def test_replace_without_file_keeps_replace_page(client, any_indexer,
                                                 any_added_issue,
                                                 indicia_image):
    replace_url = reverse('replace_image', kwargs={
      'model_name': 'issue', 'id': any_added_issue.id,
      'image_id': indicia_image.id})
    client.force_login(any_indexer)

    response = client.post(replace_url, {'comments': 'better scan'})

    assert response.status_code == 200
    html = response.content.decode()
    assert 'This field is required.' in html
    assert 'action="%s"' % replace_url in html
    assert 'alt="current image"' in html
    assert 'If you are replacing an image' in html
    assert ImageRevision.objects.count() == 0
