from types import SimpleNamespace

from django.template.base import TextNode
from django.template.loader import get_template, render_to_string
from django.template.loader_tags import BlockNode, IncludeNode
from django.urls import reverse

RELATED_LINKS = 'gcd/bits/tw_issue_related_links.html'


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


def test_related_links_show_on_narrow_screens_in_the_editing_menu():
    include, wrapper = _include_and_wrapper('editing')

    assert wrapper.rstrip().endswith('<div class="md:hidden">')


def test_related_links_list_the_issue_scans():
    issue = SimpleNamespace(id=1, indicia_image=None, soo_image=None,
                            series=SimpleNamespace(is_singleton=True))

    rendered = render_to_string(RELATED_LINKS, {'issue': issue})

    assert 'max-md:hidden' not in rendered
    assert '<a href="%s">No Issue Scans</a>' % reverse(
      'issue_images', kwargs={'issue_id': 1}) in rendered
