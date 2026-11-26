"""A help text carries the id that its field names in aria-describedby."""
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.select.views import store_select_data


class PageIds(HTMLParser):
    """The ids of a page, and the help text ids that its fields name."""

    def __init__(self, response):
        super().__init__()
        self.ids = set()
        self.help_texts = set()
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        """Note the id of the element and the help texts it names."""
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        self.help_texts.update(
          name for name in (attrs.get('aria-describedby') or '').split()
          if name.endswith('_helptext'))


@pytest.fixture
def indexer_client(client, any_indexer):
    """A client logged in as an indexer who may add."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


@pytest.mark.django_db
def test_help_texts_of_an_editing_form_have_their_ids(indexer_client,
                                                      any_added_series):
    page = PageIds(indexer_client.get(
      reverse('add_issue', kwargs={'series_id': any_added_series.id})))

    # a text field and a check box, both with a help text
    assert {'id_number_helptext', 'id_no_title_helptext'} <= page.help_texts
    assert page.help_texts <= page.ids


@pytest.mark.django_db
def test_help_text_of_the_issue_search_has_its_id(indexer_client):
    session = indexer_client.session
    store_select_data(SimpleNamespace(session=session), 'test',
                      {'issue': True, 'heading': 'Select an issue',
                       'target': 'an issue'})
    session.save()
    page = PageIds(indexer_client.get(
      reverse('select_object', kwargs={'select_key': 'test'})))

    assert 'id_issue_number_helptext' in page.help_texts
    assert page.help_texts <= page.ids
