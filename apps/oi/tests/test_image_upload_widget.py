"""The brand, feature logo and signature forms show their image field as the
image upload card."""

import io

import pytest
from PIL import Image as pyImage

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import ImageType
from apps.oi import states
from apps.oi.forms import get_revision_form
from apps.oi.forms.creator import CreatorSignatureRevisionForm
from apps.oi.forms.feature import FeatureLogoRevisionForm
from apps.oi.forms.publisher import BrandRevisionForm
from apps.oi.models import BrandRevision, Changeset, CTYPES

SCRIPT = 'js/oi/image_upload.js'
IMAGE_FIELDS = [
  (BrandRevisionForm, 'brand_emblem_image'),
  (FeatureLogoRevisionForm, 'feature_logo_image'),
  (CreatorSignatureRevisionForm, 'signature'),
]


@pytest.fixture
def media_root(tmp_path):
    """Store the uploaded files in a temporary folder."""
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


@pytest.fixture
def add_url(client, any_indexer, any_added_brand_group1):
    """Log in an indexer who may add and return the URL of the brand form."""
    any_indexer.user_permissions.add(Permission.objects.get(
      content_type__app_label='indexer', codename='can_reserve'))
    client.force_login(any_indexer)
    return reverse('add_brand_via_publisher',
                   kwargs={'publisher_id': any_added_brand_group1.parent.id})


@pytest.fixture
def changeset_one(any_indexer):
    """
    The brand form saves its image revision with changeset 1 before the view
    moves it to the new change (_create_embedded_image_revision), so a
    changeset with that id must exist.
    """
    Changeset.objects.get_or_create(id=1, defaults={
      'indexer': any_indexer, 'state': states.APPROVED,
      'change_type': CTYPES['brand']})


def _png():
    """Return a small PNG image."""
    data = io.BytesIO()
    pyImage.new('RGB', (300, 200), 'white').save(data, 'PNG')
    return data.getvalue()


@pytest.mark.parametrize('form_class, name', IMAGE_FIELDS)
def test_image_field_is_shown_as_card(form_class, name):
    """The file input is inside the card, whose drop zone is its label."""
    html = str(form_class()[name])

    assert 'data-image-upload' in html
    assert 'type="file"' in html
    assert 'name="%s"' % name in html
    assert 'id="id_%s"' % name in html
    assert 'for="id_%s"' % name in html
    assert 'max-w-md' in html


@pytest.mark.parametrize('form_class', [form for form, _ in IMAGE_FIELDS])
def test_form_media_has_card_script(form_class):
    """The pages that print form.media load the script of the card."""
    assert SCRIPT in str(form_class().media)


@pytest.mark.django_db
def test_add_brand_page_shows_card(client, add_url):
    """The page to add a brand emblem shows the card and loads its script."""
    response = client.get(add_url)

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-image-upload' in html
    assert SCRIPT in html


@pytest.mark.django_db
def test_add_brand_with_image(client, add_url, any_added_brand_group1,
                              media_root, changeset_one):
    """A brand emblem added with an image gets its image revision."""
    brand_scan, _ = ImageType.objects.get_or_create(
      name='BrandScan', defaults={'description': 'brand emblem'})

    response = client.post(add_url, {
      'name': 'Test Emblem',
      'group': [any_added_brand_group1.id],
      'brand_emblem_image': SimpleUploadedFile('emblem.png', _png(),
                                               'image/png'),
      'comments': 'scanned myself'})

    assert response.status_code == 302
    revision = BrandRevision.objects.get(name='Test Emblem')
    image = revision.image_revision
    assert image.type == brand_scan
    assert image.changeset == revision.changeset
    assert image.object_id == revision.id


@pytest.mark.django_db
def test_generic_brand_keeps_hidden_input(any_indexer, any_added_brand,
                                          any_editing_changeset):
    """A generic brand emblem keeps a hidden field instead of the card."""
    any_added_brand.generic = True
    any_added_brand.save()
    revision = BrandRevision.clone(data_object=any_added_brand,
                                   changeset=any_editing_changeset)

    form = get_revision_form(revision, user=any_indexer)(instance=revision)

    html = str(form['brand_emblem_image'])
    assert 'type="hidden"' in html
    assert 'data-image-upload' not in html
