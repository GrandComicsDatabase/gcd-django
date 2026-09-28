"""Exercise runtime HTML against the committed Tailwind build.

Tests are excluded from Tailwind's sources, so these expectations cannot
accidentally supply missing utilities to the build.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string

from apps.gcd.views.covers import get_image_tag
from apps.oi.templatetags.compare import show_diff, show_diff_markdown


ROOT = Path(__file__).resolve().parents[3]


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, attrs))


def assert_compiled(*utilities):
    css = (ROOT / 'static/css/output.css').read_text()
    for utility in utilities:
        selector = '.' + re.sub(r'([^a-zA-Z0-9_-])', r'\\\1', utility)
        assert selector in css, f'Missing runtime utility: {utility}'


@pytest.mark.parametrize('zoom,width', [(1, 100), (1.5, 150), (2, 200), (4, 400)])
@pytest.mark.parametrize('placeholder', [True, False])
def test_cover_sizes_are_discoverable_without_an_inventory(settings, zoom, width, placeholder):
    settings.FAKE_IMAGES = True
    cover = None if placeholder else SimpleNamespace(is_wraparound=False, limit_display=False)
    html = get_image_tag(cover, 'A cover', zoom)
    [(tag, attrs)] = Elements(html).elements
    assert tag == 'img'
    classes = [value for key, value in attrs if key == 'class']
    assert len(classes) == 1
    utility = f'w-[{width}px]'
    assert utility in classes[0].split()
    if placeholder:
        assert 'border-2' in classes[0].split()
    assert_compiled(utility)


@pytest.mark.parametrize('renderer', [show_diff, show_diff_markdown])
@pytest.mark.parametrize('side,utility', [('orig', 'bg-red-400'), ('new', 'bg-green-400')])
def test_diff_highlights_remain_styled_and_escape_input(renderer, side, utility):
    html = renderer([(-1, '<old>'), (1, '<new>')], side)
    assert utility in html
    highlighted = re.findall(r'<span[^>]*>(.*?)</span>', html)
    assert highlighted
    assert all('<old>' not in span and '<new>' not in span
               for span in highlighted)
    assert_compiled(utility)


@pytest.mark.parametrize('active', [False, True])
def test_crispy_tabs_keep_state_hooks_and_visibility_utilities(active):
    html = render_to_string('oi/bits/tab.html', {
        'div': SimpleNamespace(css_id='credits', css_class='tab-pane active' if active else 'tab-pane', flat_attrs=''),
        'fields': '',
    })
    tag, attrs = Elements(html).elements[0]
    classes = dict(attrs)['class'].split()
    assert tag == 'table'
    assert 'tab-pane' in classes
    assert ('active' in classes) == active
    utilities = ['block', '[&:not(.active)_table]:hidden', '[&:not(.active)_tbody]:hidden']
    assert set(utilities) <= set(classes)
    assert_compiled(*utilities)


def test_document_defaults_are_real_markup_and_locally_overridable():
    html = render_to_string('gcd/tw_base.html')
    tag, attrs = Elements(html).elements[0]
    assert tag == 'html'
    classes = dict(attrs)['class'].split()
    assert 'bg-white' in classes
    assert '[:where(&_h1)]:text-2xl' in classes
    assert_compiled(*classes)
