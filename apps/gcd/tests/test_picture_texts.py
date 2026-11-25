"""The pictures of the templates have a text for screen readers."""

import re
from pathlib import Path

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
