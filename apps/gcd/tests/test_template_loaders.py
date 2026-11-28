"""Templates are compiled once; managed content is read on each use."""

import copy

import pytest
from django.template import TemplateDoesNotExist, engines

from apps.stats.templatetags.statustags import LastUpdatedNode

PAGE = 'template_loader_test_page.html'
NOTICE = 'managed_content/gcd/messages/template_loader_test.html'


@pytest.fixture
def template_dir(settings, tmp_path):
    """Use the site's template settings with an empty template folder."""
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]['DIRS'] = [str(tmp_path)]
    settings.TEMPLATES = templates
    return tmp_path


def write(path, text):
    """Write a template file, making its folder first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def render(name):
    """Render the named template with the site's template engine."""
    return engines['django'].get_template(name).render({})


def test_template_is_compiled_once(template_dir):
    """A template is read and compiled once, then taken from the cache."""
    write(template_dir / PAGE, 'first')
    assert render(PAGE) == 'first'
    write(template_dir / PAGE, 'second')
    assert render(PAGE) == 'first'


def test_managed_content_is_read_on_each_use(template_dir):
    """A managed content template edited on disk shows at once."""
    with pytest.raises(TemplateDoesNotExist):
        render(NOTICE)
    write(template_dir / NOTICE, 'first')
    assert render(NOTICE) == 'first'
    write(template_dir / NOTICE, 'second')
    assert render(NOTICE) == 'second'


def test_cached_page_includes_current_managed_content(template_dir):
    """A page from the cache shows the managed content as it is now."""
    write(template_dir / PAGE, '<{% include "' + NOTICE + '" %}>')
    write(template_dir / NOTICE, 'first')
    assert render(PAGE) == '<first>'
    write(template_dir / NOTICE, 'second')
    assert render(PAGE) == '<second>'


@pytest.mark.parametrize('debug', [False, True])
def test_template_debug_follows_debug(settings, debug):
    """Template debug data follows DEBUG, also when settings_local sets it."""
    settings.DEBUG = debug
    assert engines['django'].engine.debug is debug


@pytest.mark.django_db
def test_last_updated_issues_keeps_no_state_on_the_node():
    """
    Rendering the tag leaves its node as it was parsed.

    A compiled template is shared by all the requests of a process, also
    by those served at the same time, so a value that one render stores
    on the node can be read by another.
    """
    template = engines['django'].from_string(
        '{% load statustags %}{% last_updated_issues language=code %}')
    assert template.render({'code': 'de'}) == '<ul></ul>'
    node, = template.template.nodelist.get_nodes_by_type(LastUpdatedNode)
    assert node.language_code is None
