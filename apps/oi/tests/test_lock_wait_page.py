"""
When the database gives up on a lock wait or breaks a deadlock, the user gets
a page that says so, and the request has saved nothing.
"""
import pytest
from django.db import OperationalError
from django.urls import path

from apps.indexer.models import Error
from urls import urlpatterns as site_patterns

KEY = 'written by the failed request'
MESSAGE = ('Another request was saving the same data at this moment, so '
           'nothing was saved. Please try again.')


def _failing_view(request, code):
    """Write a row, then fail as the database would."""
    Error.objects.create(error_key=KEY, is_safe=False, error_text='text')
    raise OperationalError(code, 'from the test')


urlpatterns = [path('failing/<int:code>/', _failing_view)] + site_patterns


@pytest.mark.django_db
@pytest.mark.urls(__name__)
@pytest.mark.parametrize('code', [1205, 1213])
def test_a_lock_conflict_gets_a_page(client, caplog, code):
    """
    A lock conflict gives the page with status 503, saves nothing and is
    logged: by the middleware with its traceback, by Django as the error
    that a 5xx answer is.
    """
    response = client.get('/failing/%d/' % code)

    assert response.status_code == 503
    assert MESSAGE in response.content.decode()
    assert not Error.objects.filter(error_key=KEY).exists()
    assert 'Lock conflict on /failing/%d/' % code in caplog.text
    assert [record.levelname for record in caplog.records
            if record.name == 'django.request'] == ['ERROR']


@pytest.mark.django_db
@pytest.mark.urls(__name__)
def test_another_database_error_stays_an_error(client):
    """Any other database error reaches the usual error handling."""
    with pytest.raises(OperationalError):
        client.get('/failing/2006/')
