"""
Read the forms and links of a rendered page, so that a test submits and
follows them as a browser would, and the ids of the page, which must be
unique.
"""
from collections import Counter
from html.parser import HTMLParser

# Inputs that a browser leaves out of the data of a form unless they are
# clicked, or that carry a file.
NOT_SUBMITTED = ('submit', 'button', 'reset', 'image', 'file')


class PageForms(HTMLParser):
    """
    The ids of a page, its links and its forms, in page order: for each
    form its method, action and the (name, value) pairs that a browser
    would submit.
    """

    def __init__(self, html):
        super().__init__()
        self.ids = []
        self.links = []
        self.forms = []
        self._form = None
        self._select = None
        self._textarea = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        """Collect ids, links, forms and the values of their fields."""
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if tag == 'form':
            self._form = {'method': attrs.get('method', 'get').upper(),
                          'action': attrs.get('action', ''), 'fields': []}
            self.forms.append(self._form)
        elif self._form is None or 'disabled' in attrs:
            return
        elif tag == 'input' and 'name' in attrs:
            kind = attrs.get('type', 'text')
            if kind in NOT_SUBMITTED:
                return
            if kind in ('checkbox', 'radio') and 'checked' not in attrs:
                return
            default = 'on' if kind in ('checkbox', 'radio') else ''
            self._form['fields'].append((attrs['name'],
                                         attrs.get('value', default)))
        elif tag == 'select' and 'name' in attrs:
            # A list box shows several options and may submit none.
            single = 'multiple' not in attrs and \
                int(attrs.get('size') or 1) <= 1
            self._select = {'name': attrs['name'], 'single': single,
                            'first': None, 'selected': []}
        elif tag == 'option' and self._select:
            value = attrs.get('value', '')
            if self._select['first'] is None:
                self._select['first'] = value
            if 'selected' in attrs:
                self._select['selected'].append(value)
        elif tag == 'textarea' and 'name' in attrs:
            self._textarea = [attrs['name'], '']

    def handle_data(self, data):
        """Keep the text of a textarea."""
        if self._textarea:
            self._textarea[1] += data

    def handle_endtag(self, tag):
        """Close a form, and add the values of a select or a textarea."""
        if tag == 'form':
            self._form = None
        elif tag == 'select' and self._select:
            values = self._select['selected']
            if self._select['single']:
                # A drop-down without a selected option submits its first.
                values = values[-1:] or [self._select['first']]
            for value in values:
                if value is not None:
                    self._form['fields'].append((self._select['name'],
                                                 value))
            self._select = None
        elif tag == 'textarea' and self._textarea:
            name, text = self._textarea
            # A browser drops the line break that follows the start tag.
            if text.startswith('\r\n'):
                text = text[2:]
            elif text.startswith('\n'):
                text = text[1:]
            self._form['fields'].append((name, text))
            self._textarea = None

    def repeated_ids(self):
        """Return the ids that the page gives to more than one element."""
        return sorted(name for name, count in Counter(self.ids).items()
                      if count > 1)

    def link(self, part):
        """Return the only link of the page whose address holds part."""
        links = [link for link in self.links if part in link]
        assert len(links) == 1, links
        return links[0]

    def form(self, method, action):
        """Return the only form of the page with method and action."""
        forms = [form for form in self.forms
                 if (form['method'], form['action']) == (method, action)]
        assert len(forms) == 1, forms
        return forms[0]

    @staticmethod
    def data(form, **chosen):
        """
        Return the data that form submits, as a dict of lists, with the
        values that the user chose in place of the rendered ones.
        """
        data = {}
        for name, value in form['fields']:
            data.setdefault(name, []).append(value)
        for name, value in chosen.items():
            data[name] = [value]
        return data
