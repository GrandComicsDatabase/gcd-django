"""The search field and the buttons of the top bar have a name."""

from html.parser import HTMLParser

import pytest

PAGES = ['/', '/no-such-page/']


class _TopBarParser(HTMLParser):
    """
    Reads the top bar, the first <nav> of a page: the attributes of its
    search fields, and the attributes and the text of each of its buttons.
    """

    def __init__(self):
        super().__init__()
        self.nav_depth = 0
        self.top_bar_read = False
        self.in_button = False
        self.search_fields = []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        if self.top_bar_read:
            return
        attributes = dict(attrs)
        if tag == 'nav':
            self.nav_depth += 1
        if not self.nav_depth:
            return
        if tag == 'input' and attributes.get('type') == 'search':
            self.search_fields.append(attributes)
        elif tag == 'button':
            self.buttons.append({'attributes': attributes, 'text': ''})
            self.in_button = True

    def handle_endtag(self, tag):
        if tag == 'button':
            self.in_button = False
        elif tag == 'nav' and self.nav_depth:
            self.nav_depth -= 1
            self.top_bar_read = not self.nav_depth

    def handle_data(self, data):
        if self.nav_depth and self.in_button:
            self.buttons[-1]['text'] += data


def _name(attributes, text=''):
    """
    The name a screen reader announces: the aria-label, otherwise the
    text inside the element, the title of a drawing included.
    """
    if attributes.get('aria-label'):
        return attributes['aria-label'].strip()
    return ' '.join(text.split())


def _top_bar(client, address):
    """The search fields and the buttons of the top bar of the page."""
    response = client.get(address)
    parser = _TopBarParser()
    parser.feed(response.content.decode())
    assert parser.top_bar_read, 'the page has no top bar'
    return parser


def _buttons_with_class(top_bar, css_class):
    """The names of the buttons of the top bar with the class."""
    return [_name(button['attributes'], button['text'])
            for button in top_bar.buttons
            if css_class in button['attributes'].get('class', '').split()]


@pytest.mark.django_db
@pytest.mark.parametrize('address', PAGES)
def test_search_field_is_named_search(client, address):
    """The field had only a placeholder, which is no name."""
    top_bar = _top_bar(client, address)

    assert [_name(field) for field in top_bar.search_fields] == ['Search']


@pytest.mark.django_db
@pytest.mark.parametrize('address', PAGES)
def test_search_button_is_named_search(client, address):
    """The button held only the drawing of a magnifier."""
    top_bar = _top_bar(client, address)

    names = [_name(button['attributes'], button['text'])
             for button in top_bar.buttons
             if button['attributes'].get('type') == 'submit']
    assert names == ['Search']


@pytest.mark.django_db
@pytest.mark.parametrize('address', PAGES)
def test_menu_button_is_named_menu(client, address):
    """The button was announced by the title of its drawing."""
    top_bar = _top_bar(client, address)

    names = _buttons_with_class(top_bar, 'mobile-menu-button-gcd-md')
    assert names == ['Menu']


@pytest.mark.django_db
@pytest.mark.parametrize('address', PAGES)
def test_user_menu_buttons_are_named_user_menu(client, address):
    """The buttons held only an image without a text."""
    top_bar = _top_bar(client, address)

    names = _buttons_with_class(top_bar, 'dropdown-toggle')
    assert names == ['User menu', 'User menu']


@pytest.mark.django_db
@pytest.mark.parametrize('address', PAGES)
def test_every_button_of_the_top_bar_has_a_name(client, address):
    """No button of the bar is announced as a bare "button"."""
    top_bar = _top_bar(client, address)

    names = [_name(button['attributes'], button['text'])
             for button in top_bar.buttons]
    assert names and all(names), names
