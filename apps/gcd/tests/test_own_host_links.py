"""The site links its own hosts with https, not with http."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# www, my, docs, beta and errors, the hosts of the GCD itself
OWN_HOST_HTTP = re.compile(
  r'http://(?:www\.|docs\.|my\.|beta\.|errors\.)?comics\.org')

TEXT_SUFFIXES = {'.html', '.txt', '.xml', '.po', '.md', '.py'}


def _site_files():
    """The text files of the site: templates, static files, translations
    and the code of the apps, without tests and migrations."""
    for folder in ('templates', 'static', 'locale', 'apps'):
        for path in (ROOT / folder).rglob('*'):
            parts = path.relative_to(ROOT).parts
            if path.suffix in TEXT_SUFFIXES and path.is_file() and \
               'tests' not in parts and 'migrations' not in parts:
                yield path


def test_own_hosts_are_linked_with_https():
    """No template, static file, translation or code links the GCD's
    own hosts with http."""
    found = ['%s:%d' % (path.relative_to(ROOT), number)
             for path in _site_files()
             for number, line in enumerate(
               path.read_text(encoding='utf-8', errors='replace')
                   .splitlines(), 1)
             if OWN_HOST_HTTP.search(line)]

    assert found == []
