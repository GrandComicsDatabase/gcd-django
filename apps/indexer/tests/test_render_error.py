"""
An error page reached through a redirect gets its text from the messages
of the session, not from a row of the errors table.
"""
import pytest
from django.contrib import messages
from django.http import HttpResponse
from django.urls import path, reverse

from apps.indexer.models import Error
from apps.indexer.views import render_error
from urls import urlpatterns as site_patterns

TEXT = 'Some error text.'
UNKNOWN = 'Unknown error.'


def _plain_error(request):
    """Redirect to the error page with a text to escape."""
    return render_error(request, TEXT + ' <b>bold</b>')


def _safe_error(request):
    """Redirect to the error page with a text that keeps its HTML."""
    return render_error(request, TEXT + ' <b>bold</b>', is_safe=True)


def _other_message(request):
    """Leave a message for a later page, as My Comics does."""
    messages.success(request, 'Item saved.')
    return HttpResponse('saved')


def _pending_messages(request):
    """Show the messages that are still waiting for a page."""
    return HttpResponse(' | '.join(str(message) for message
                                   in messages.get_messages(request)))


urlpatterns = [
  path('plain/', _plain_error),
  path('safe/', _safe_error),
  path('other/', _other_message),
  path('pending/', _pending_messages),
] + site_patterns


@pytest.mark.django_db
@pytest.mark.urls(__name__)
def test_redirect_writes_no_row(client):
    """The redirect goes to the error page without a key or a row."""
    response = client.get('/plain/')

    assert response.status_code == 302
    assert response['Location'] == reverse('error')
    assert not Error.objects.exists()


@pytest.mark.django_db
@pytest.mark.urls(__name__)
def test_page_shows_the_escaped_text(client):
    """The page shows the text once, with its HTML escaped."""
    content = client.get('/plain/', follow=True).content.decode()

    assert content.count(TEXT) == 1
    assert '&lt;b&gt;bold&lt;/b&gt;' in content
    assert UNKNOWN not in content


@pytest.mark.django_db
@pytest.mark.urls(__name__)
def test_safe_text_keeps_its_html(client):
    """A text given as safe reaches the page with its HTML."""
    content = client.get('/safe/', follow=True).content.decode()

    assert TEXT + ' <b>bold</b>' in content


@pytest.mark.django_db
@pytest.mark.urls(__name__)
def test_second_load_is_an_unknown_error(client):
    """The text is shown once; loading the page again finds none."""
    response = client.get('/plain/')
    client.get(response['Location'])
    content = client.get(response['Location']).content.decode()

    assert TEXT not in content
    assert UNKNOWN in content


@pytest.mark.django_db
@pytest.mark.urls(__name__)
def test_other_messages_wait_for_their_page(client):
    """A message left for another page is neither shown nor lost."""
    client.get('/other/')
    content = client.get('/plain/', follow=True).content.decode()

    assert TEXT in content
    assert 'Item saved.' not in content
    assert client.get('/pending/').content.decode() == 'Item saved.'


@pytest.mark.django_db
def test_key_of_an_old_link_still_works(client):
    """A link with the key of a row in the table shows its text once."""
    Error.objects.create(error_key='old', error_text=TEXT)
    url = reverse('error') + '?error_key=old'

    assert TEXT in client.get(url).content.decode()
    assert not Error.objects.exists()
    assert UNKNOWN in client.get(url).content.decode()
