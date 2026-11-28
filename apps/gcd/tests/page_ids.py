# -*- coding: utf-8 -*-
"""
A check of the ids of a rendered page, for the tests of the pages of
the cover images.
"""
from html.parser import HTMLParser


class _IdParser(HTMLParser):
    """
    Collects the ids of a page and the ids named by its labels.
    """
    def __init__(self):
        """
        Starts with no ids.
        """
        super().__init__()
        self.ids = []
        self.label_targets = []

    def handle_starttag(self, tag, attrs):
        """
        Keeps the id of the element and the target of a label.
        """
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'label' and attrs.get('for'):
            self.label_targets.append(attrs['for'])


def assert_valid_ids(content):
    """
    Every id of the page is used once and every label names an element of
    the page.
    """
    parser = _IdParser()
    parser.feed(content)
    duplicates = {id_ for id_ in parser.ids if parser.ids.count(id_) > 1}
    assert not duplicates
    assert not set(parser.label_targets) - set(parser.ids)
