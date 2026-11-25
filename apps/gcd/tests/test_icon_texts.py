"""The icons of the templates have a text for screen readers."""

import re
from pathlib import Path

from django.template.loader import get_template

from apps.gcd.templatetags.credits import show_country_info

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = sorted([*ROOT.glob('templates/**/*.html'),
                    *ROOT.glob('apps/*/templates/**/*.html')])
# A start tag; a {% %} or {{ }} inside it may hold a ">".
START_TAG = r'<%s\b(?:\{%%.*?%%\}|\{\{.*?\}\}|[^>])*>'
IMG = re.compile(START_TAG % 'img', re.IGNORECASE | re.DOTALL)
BUTTON = re.compile(START_TAG % 'button', re.IGNORECASE | re.DOTALL)
# An icon is a file of the site; show_country_info writes a flag.
ICON = re.compile(r'\{%\s*static\s|STATIC_URL|show_country_info')
ALT = re.compile(r'\salt\s*=', re.IGNORECASE)
THREE_BARS = re.compile(
    r'\{%\s*include\s+["\']gcd/bits/tw_three_bars\.html["\']')


def _place(path, text, position):
    """Return the place of the position in the text as 'file:line'."""
    return '%s:%d' % (path.relative_to(ROOT),
                      text.count('\n', 0, position) + 1)


def _icons_without_alt():
    """
    Return the place and the text of each <img> of the templates that
    shows an icon and has no alt attribute.
    """
    missing = []
    for path in TEMPLATES:
        text = path.read_text(encoding='utf-8')
        for tag in IMG.finditer(text):
            html = ' '.join(tag.group().split())
            has_alt = ALT.search(html) or 'show_country_info' in html
            if ICON.search(html) and not has_alt:
                missing.append('%s %s' % (_place(path, text, tag.start()),
                                          html))
    return missing


def _buttons_with_three_bars():
    """
    Return the place and the start tag of each button of the templates
    that holds the drawing of three bars.
    """
    buttons = []
    for path in TEMPLATES:
        text = path.read_text(encoding='utf-8')
        for include in THREE_BARS.finditer(text):
            place = _place(path, text, include.start())
            starts = list(BUTTON.finditer(text, 0, include.start()))
            assert starts, '%s: the drawing is in no button' % place
            button = starts[-1]
            assert '</button>' not in text[button.end():include.start()], \
                '%s: the drawing is in no button' % place
            buttons.append((_place(path, text, button.start()),
                            ' '.join(button.group().split())))
    return buttons


def test_every_icon_of_the_templates_has_an_alt():
    """
    An icon needs an alt: empty when the text next to it says the same,
    else what the icon means. A flag gets its alt from show_country_info.
    """
    assert 'alt="ZZ"' in show_country_info(None)

    assert _icons_without_alt() == []


def test_the_drawing_of_three_bars_is_hidden_from_screen_readers():
    """Its title, "bars-3-bottom-left", was read out as a name."""
    drawing = get_template('gcd/bits/tw_three_bars.html').render()

    svg = re.search(START_TAG % 'svg', drawing, re.DOTALL).group()
    assert 'aria-hidden="true"' in svg


def test_every_button_with_the_drawing_of_three_bars_has_a_name():
    """The title of the drawing was the only name of these buttons."""
    buttons = _buttons_with_three_bars()

    assert buttons
    assert [place for place, tag in buttons
            if not re.search(r'\saria-label="[^"]+"', tag)] == []
