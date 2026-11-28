"""The pictures of the templates have a text for screen readers."""

import io
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from PIL import Image as pyImage

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.templatetags.static import static
from django.test import override_settings

from apps.gcd.models import Creator, CreatorNameDetail, Image, ImageType
from apps.oi import states
from apps.oi.models import CTYPES, Changeset, ImageRevision
from apps.stddata.models import Date, Script

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = sorted([*ROOT.glob('templates/**/*.html'),
                    *ROOT.glob('apps/*/templates/**/*.html')])
# An <img> start tag; a {% %} or {{ }} inside it may hold a ">".
IMG = re.compile(r'<img\b(?:\{%.*?%\}|\{\{.*?\}\}|[^>])*>',
                 re.IGNORECASE | re.DOTALL)
# An icon, a file of the site or a flag that show_country_info writes, is
# not a picture.
ICON = re.compile(r'\{%\s*static\s|STATIC_URL|show_country_info')
ALT = re.compile(r'\salt\s*=', re.IGNORECASE)


def _pictures_without_alt():
    """
    Return the place, as 'file:line', and the text of each <img> of the
    templates that shows a picture and has no alt attribute.
    """
    missing = []
    for path in TEMPLATES:
        text = path.read_text(encoding='utf-8')
        for tag in IMG.finditer(text):
            html = ' '.join(tag.group().split())
            if not ICON.search(html) and not ALT.search(html):
                line = text.count('\n', 0, tag.start()) + 1
                missing.append('%s:%d %s' % (path.relative_to(ROOT), line,
                                             html))
    return missing


def test_every_picture_of_the_templates_has_an_alt():
    """
    A picture needs an alt: empty when the text next to it says the
    same, else what it shows or, alone in a link, where the link leads.
    """
    assert _pictures_without_alt() == []


# The alt of a portrait that is alone in its link to the compare page of
# the portrait's change.
PORTRAIT_LINK = 'Change of the portrait'


class _Pictures(HTMLParser):
    """
    Read a page: each <img> as (src, alt, address of the link it is in or
    None), and the address of each link that a next link finds open.
    """

    def __init__(self):
        """Start outside any link."""
        super().__init__()
        self.link = None
        self.pictures = []
        self.unclosed = []

    def handle_starttag(self, tag, attrs):
        """Note each link, and each picture with the link it is in."""
        attrs = dict(attrs)
        if tag == 'a':
            if self.link is not None:
                self.unclosed.append(self.link)
            self.link = attrs.get('href')
        elif tag == 'img':
            self.pictures.append((attrs.get('src'), attrs.get('alt'),
                                  self.link))

    def handle_endtag(self, tag):
        """Leave the link at its end tag."""
        if tag == 'a':
            self.link = None


def _creator_page(client, creator):
    """Return the creator page of creator, read by _Pictures."""
    response = client.get(creator.get_absolute_url())
    assert response.status_code == 200
    page = _Pictures()
    page.feed(response.content.decode())
    return page


@pytest.fixture
def creator(db):
    """A creator with an official name and no portrait."""
    Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})
    creator = Creator.objects.create(
        gcd_official_name='Some Creator', sort_name='Creator, Some',
        birth_date=Date.objects.create(year='1950'),
        death_date=Date.objects.create())
    CreatorNameDetail.objects.create(creator=creator, name='Some Creator',
                                     is_official_name=True)
    return creator


@pytest.fixture
def portrait(creator, tmp_path):
    """The portrait of the creator and the approved change that added it."""
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        portrait_type, _ = ImageType.objects.get_or_create(
            id=4, defaults={'name': 'CreatorPortrait',
                            'description': 'portrait image'})
        image = Image.objects.create(
            content_type=ContentType.objects.get_for_model(creator),
            object_id=creator.id, type=portrait_type)
        data = io.BytesIO()
        pyImage.new('RGB', (60, 80), 'white').save(data, 'PNG')
        image.image_file.save('portrait.png', ContentFile(data.getvalue()))
        changeset = Changeset.objects.create(
            indexer=User.objects.create_user('portrait_indexer'),
            state=states.APPROVED, change_type=CTYPES['image'])
        ImageRevision.objects.create(
            changeset=changeset, image=image, type=portrait_type,
            content_type=image.content_type, object_id=creator.id)
        yield image, changeset


def test_creator_page_names_where_the_portrait_links_lead(client, creator,
                                                          portrait):
    """
    Both pictures of the portrait are alone in a closed link to the
    compare page of its change, and their alt says so.
    """
    image, changeset = portrait
    compare = '/changeset/%d/compare/' % changeset.id

    page = _creator_page(client, creator)

    linked = [(src, alt) for src, alt, link in page.pictures
              if link == compare]
    assert linked == [(image.cropped_face_url, PORTRAIT_LINK),
                      (image.scaled_image_url, PORTRAIT_LINK)]
    assert compare not in page.unclosed


def test_creator_page_placeholder_portrait_is_no_link(client, creator):
    """
    Without a portrait the placeholder is a picture with an empty alt and
    not a link: there is no change of a portrait to lead to.
    """
    avatar = static('img/avatar.png')

    page = _creator_page(client, creator)

    assert [picture for picture in page.pictures
            if picture[0] == avatar] == [(avatar, '', None)]
