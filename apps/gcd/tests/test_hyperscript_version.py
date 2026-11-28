"""The pop-up windows ask unpkg.com for one fixed version of hyperscript."""

import re
from pathlib import Path

from django.conf import settings
from django.template.utils import get_app_template_dirs

# Without "@<major>.<minor>.<patch>" unpkg.com sends whatever release came
# out last, so a new release reaches the site unannounced.
UNVERSIONED = re.compile(r'unpkg\.com/hyperscript\.org(?!@\d+\.\d+\.\d+)')


def test_hyperscript_is_loaded_at_a_fixed_version():
    folders = [*settings.TEMPLATES[0]['DIRS'],
               *get_app_template_dirs('templates')]
    found = []
    for folder in folders:
        for path in Path(folder).rglob('*.html'):
            text = path.read_text(encoding='utf-8', errors='replace')
            if UNVERSIONED.search(text):
                found.append(path.name)
    assert found == []
