"""Exercise runtime HTML against the committed Tailwind build.

Tests are excluded from Tailwind's sources, so these expectations cannot
accidentally supply missing utilities to the build.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
from types import SimpleNamespace

import django_tables2 as tables
import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory

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
def test_cover_sizes_are_discoverable_without_an_inventory(
        settings, zoom, width, placeholder):
    settings.FAKE_IMAGES = True
    cover = None if placeholder else SimpleNamespace(
        is_wraparound=False, limit_display=False)
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
@pytest.mark.parametrize('side,utility', [
    ('orig', 'bg-red-400'), ('new', 'bg-green-400'),
])
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
        'div': SimpleNamespace(
            css_id='credits',
            css_class='tab-pane active' if active else 'tab-pane',
            flat_attrs='',
        ),
        'fields': '',
    })
    tag, attrs = Elements(html).elements[0]
    classes = dict(attrs)['class'].split()
    assert tag == 'table'
    assert 'tab-pane' in classes
    assert ('active' in classes) == active
    utilities = ['block', '[&:not(.active)_table]:hidden',
                 '[&:not(.active)_tbody]:hidden']
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


def test_document_link_hover_is_guarded_by_device_capability():
    html = render_to_string('gcd/tw_base.html')
    _, attrs = Elements(html).elements[0]
    utility = '[@media(hover:hover)]:[:where(&_a:hover)]:underline'
    assert utility in dict(attrs)['class'].split()
    css = (ROOT / 'static/css/output.css').read_text()
    selector = '.' + re.sub(r'([^a-zA-Z0-9_-])', r'\\\1', utility)
    # Check the compiled rule's enclosing blocks, not just its class name.
    position = css.index(':where(' + selector + ' a:hover)')
    blocks = []
    start = 0
    for match in re.finditer(r'[{}]', css[:position]):
        if match.group() == '{':
            blocks.append(css[start:match.start()].strip())
        else:
            blocks.pop()
        start = match.end()
    assert any(re.fullmatch(r'@media\s*\(hover:\s*hover\)', block)
               for block in blocks)
    assert '[:where(&_a:hover)]:underline' not in dict(attrs)['class'].split()


@pytest.mark.parametrize('attrs', [{}, {'class': 'w-full', 'id': 'results'}])
def test_sortable_table_has_one_class_attribute_and_styles_its_body(attrs):
    class ExampleTable(tables.Table):
        name = tables.Column()

    table = ExampleTable([{'name': 'Example'}], attrs=attrs)
    table.no_export = True
    html = render_to_string('gcd/bits/tw_sortable_table.html', {'table': table},
                            request=RequestFactory().get('/'))
    elements = Elements(html).elements
    table_attrs = next(values for tag, values in elements if tag == 'table')
    classes = [value for key, value in table_attrs if key == 'class']
    assert classes == [attrs.get('class', 'border')]
    if 'id' in attrs:
        assert dict(table_attrs)['id'] == attrs['id']
    body_attrs = next(values for tag, values in elements if tag == 'tbody')
    utilities = dict(body_attrs)['class'].split()
    assert '[:where(&)_tr]:flex' in utilities
    assert 'sm:[:where(&)_tr]:table-row' in utilities
    assert_compiled(*(utility for utility in utilities
                      if utility != 'sortable_listing'))


@pytest.mark.parametrize('mycomics_red', [False, True])
@pytest.mark.parametrize('number', [1, 2, 3])
def test_pagination_selects_one_hover_color_per_control(mycomics_red, number):
    page = SimpleNamespace(
        number=number, has_other_pages=True, has_previous=number > 1,
        has_next=number < 3, previous_page_number=number - 1,
        next_page_number=number + 1, page_range=[1, None, 3],
        paginator=SimpleNamespace(num_pages=3),
    )
    html = render_to_string('gcd/bits/tw_pagination_bar.html', {
        'page': page, 'mycomics_red': mycomics_red,
    })
    color = 'red' if mycomics_red else 'blue'
    controls = []
    for tag, attrs in Elements(html).elements:
        classes = dict(attrs).get('class', '').split()
        if 'navigation-bar-box-link' not in classes:
            continue
        hover = [name for name in classes if name.startswith('hover:bg-')]
        assert len(hover) == 1
        assert hover[0].startswith(f'hover:bg-{color}-')
        if tag == 'span' and f'bg-{color}-300' not in classes:
            assert hover == [f'hover:bg-{color}-100']
        assert_compiled(*hover)
        controls.append(hover)
    assert controls


@pytest.mark.parametrize('count', [1, 2])
def test_alpha_pagination_selects_one_hover_color(count):
    pages = [SimpleNamespace(number=number) for number in range(count)]
    html = render_to_string('gcd/bits/tw_alpha_pagination_bar.html', {
        'alpha_paginator': SimpleNamespace(page_range=pages),
    })
    links = [dict(attrs) for tag, attrs in Elements(html).elements if tag == 'a']
    assert len(links) == count
    for attrs in links:
        hover = [name for name in attrs['class'].split()
                 if name.startswith('hover:bg-')]
        assert hover == ['hover:bg-blue-100' if count == 1
                         else 'hover:bg-blue-300']
