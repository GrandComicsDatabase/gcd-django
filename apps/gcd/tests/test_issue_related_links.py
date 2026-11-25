import re
from types import SimpleNamespace

import pytest

from django.core.management import call_command
from django.template.base import TextNode
from django.template.loader import get_template, render_to_string
from django.template.loader_tags import BlockNode, IncludeNode
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Issue

RELATED_LINKS = 'gcd/bits/tw_issue_related_links.html'


def _compact(html):
    """
    The HTML without the whitespace between tags, and with other runs of
    whitespace as one space.
    """
    return re.sub(r'\s+', ' ', re.sub(r'>\s+<', '><', html)).strip()


def _include_and_wrapper(block_name):
    """
    The include of the Related Links in a block of the issue page, with the
    markup just before it.
    """
    template = get_template('gcd/details/tw_issue.html').template
    block = next(node for node in template.nodelist.get_nodes_by_type(
                   BlockNode) if node.name == block_name)
    nodes = list(block.nodelist)
    for index, node in enumerate(nodes):
        if isinstance(node, IncludeNode) and \
           node.template.var == RELATED_LINKS:
            previous = nodes[index - 1]
            assert isinstance(previous, TextNode)
            return node, previous.s
    raise AssertionError('No Related Links in block %s' % block_name)


def test_related_links_show_on_wide_screens_in_the_side_column():
    include, wrapper = _include_and_wrapper('issue_links')

    assert wrapper.rstrip().endswith('<div class="max-md:hidden">')


def test_related_links_show_on_narrow_screens_in_the_menu():
    # change_history is shown on my.comics.org too, editing is not
    include, wrapper = _include_and_wrapper('change_history')

    assert wrapper.rstrip().endswith('<div class="md:hidden">')


def test_related_links_list_the_issue_scans():
    issue = SimpleNamespace(id=1, indicia_image=None, soo_image=None,
                            series=SimpleNamespace(is_singleton=True))

    rendered = render_to_string(RELATED_LINKS, {'issue': issue})

    assert 'max-md:hidden' not in rendered
    assert '<a href="%s">No Issue Scans</a>' % reverse(
      'issue_images', kwargs={'issue_id': 1}) in rendered


@pytest.mark.django_db
@pytest.mark.parametrize('mycomics', (False, True))
@pytest.mark.parametrize('wrapper', ('max-md:hidden', 'md:hidden'))
def test_issue_page_has_the_related_links_for_each_width(client, wrapper,
                                                         mycomics):
    call_command('seed_development_data')
    issue = Issue.objects.filter(variant_of=None, deleted=False).first()

    with override_settings(MYCOMICS=mycomics):
        response = client.get(reverse('show_issue',
                                      kwargs={'issue_id': issue.id}))

    assert response.status_code == 200
    links = render_to_string(RELATED_LINKS, {
      'issue': response.context['issue'],
      'cover_page': response.context.get('cover_page')})
    assert 'No Issue Scans' in links
    page = _compact(response.content.decode())
    assert page.count(_compact(links)) == 2
    assert page.count(_compact('<div class="%s">%s</div>'
                               % (wrapper, links))) == 1
