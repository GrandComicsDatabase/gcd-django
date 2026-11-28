import re
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

from django.test import override_settings

from apps.gcd.models.cover import ZOOM_LARGE, ZOOM_MEDIUM, ZOOM_SMALL
from apps.gcd.views.covers import get_image_tag
from apps.oi.templatetags.compare import field_value


def _glued_attributes(html):
    """
    Return the characters that follow a quoted attribute value directly.

    In HTML a quoted attribute value must be followed by whitespace, '/' or
    '>'; anything else is the parse error of attributes without a space.
    """
    return re.findall(r'="[^"]*"([^\s/>])', html)


def _img_attributes(html):
    """Return the attributes of the first img tag of html as a dict."""
    found = []

    class Parser(HTMLParser):
        """Keep the attributes of the first img tag in found."""

        def handle_starttag(self, tag, attrs):
            """Store the attributes of an img tag if none is stored yet."""
            if tag == 'img' and not found:
                found.append(dict(attrs))

    Parser().feed(html)
    return found[0]


@pytest.mark.parametrize('zoom_level', [ZOOM_SMALL, ZOOM_MEDIUM, ZOOM_LARGE])
@pytest.mark.parametrize('can_have_cover, alt', [(True, 'No image yet'),
                                                 (False, 'No image')])
def test_placeholder_without_cover_has_spaced_attributes(zoom_level,
                                                         can_have_cover, alt):
    """The placeholder of an issue without a cover is valid HTML."""
    tag = get_image_tag(None, 'Cover for Test Series #1', zoom_level,
                        can_have_cover=can_have_cover)
    assert _glued_attributes(tag) == []
    assert _img_attributes(tag)['alt'] == alt


def test_placeholder_of_limited_cover_has_spaced_attributes():
    """The placeholder shown for a cover with limited display is valid."""
    cover = SimpleNamespace(limit_display=True, is_wraparound=False)
    tag = get_image_tag(cover, 'Cover for Test Series #1', ZOOM_MEDIUM)
    assert _glued_attributes(tag) == []
    assert _img_attributes(tag)['alt'] == 'No image yet'


def _img_class_values(html):
    """Return the values of every class attribute of the first img tag."""
    found = []

    class Parser(HTMLParser):
        """Keep the attribute list of the first img tag in found."""

        def handle_starttag(self, tag, attrs):
            """Store the attribute list of an img tag if none is stored."""
            if tag == 'img' and not found:
                found.append(attrs)

    Parser().feed(html)
    return [value for name, value in found[0] if name == 'class']


@pytest.mark.parametrize('zoom_level, width', [(ZOOM_SMALL, 100),
                                               (ZOOM_MEDIUM, 200),
                                               (ZOOM_LARGE, 400)])
@pytest.mark.parametrize('can_have_cover', [True, False])
def test_placeholder_without_cover_has_one_class(zoom_level, width,
                                                 can_have_cover):
    """The border and the width of the placeholder are in one class."""
    tag = get_image_tag(None, 'Cover for Test Series #1', zoom_level,
                        can_have_cover=can_have_cover)
    classes = _img_class_values(tag)
    assert len(classes) == 1
    assert 'border-2' in classes[0].split()
    assert 'w-[%spx]' % width in classes[0].split()


def test_placeholder_of_limited_cover_has_one_class():
    """The placeholder of a cover with limited display has one class."""
    cover = SimpleNamespace(limit_display=True, is_wraparound=False)
    tag = get_image_tag(cover, 'Cover for Test Series #1', ZOOM_MEDIUM)
    classes = _img_class_values(tag)
    assert len(classes) == 1
    assert classes[0].split()[:2] == ['border-2', 'cover_img']


@override_settings(FAKE_IMAGES=False)
def test_compare_brand_emblem_has_spaced_attributes():
    """The emblem image that field_value builds for a brand is valid."""
    brand = SimpleNamespace(
      emblem=SimpleNamespace(icon_url='/media/emblem.png'),
      get_absolute_url=lambda: '/brand/1/')
    value = field_value(SimpleNamespace(brand=brand), 'brand')
    assert _glued_attributes(value) == []
    assert _img_attributes(value) == {'class': 'inline',
                                      'src': '/media/emblem.png'}
