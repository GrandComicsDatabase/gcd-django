"""Shared pytest fixtures for the v2 API test suite.

Three groups:

* ``country`` / ``language`` — minimal stddata rows for foreign keys.
* ``publisher`` / ``series`` / ``issue`` — chained GcdData fixtures
  ready to drop into endpoint tests in subsequent sprints.
* ``api_client`` / ``authenticated_user`` / ``authenticated_token`` /
  ``authenticated_client`` — DRF test client and a ``Token``-backed
  variant so view tests can flip between anon and authed in one line.
"""

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.gcd.models import Issue, Publisher, Series
from apps.stddata.models import Country, Language


@pytest.fixture
def country(db):
    """Return a minimal ``Country`` row fit for foreign keys."""
    obj, _ = Country.objects.get_or_create(
        code='xz',
        defaults={'name': 'Test Country'},
    )
    return obj


@pytest.fixture
def language(db):
    """Return a minimal ``Language`` row fit for foreign keys."""
    obj, _ = Language.objects.get_or_create(
        code='xz',
        defaults={'name': 'Test Language'},
    )
    return obj


@pytest.fixture
def publisher(db, country):
    """Return a saved ``Publisher`` tied to ``country``."""
    return Publisher.objects.create(
        name='Test Publisher',
        year_began=1960,
        notes='',
        country=country,
    )


@pytest.fixture
def series(db, publisher, country, language):
    """Return a saved ``Series`` tied to ``publisher``."""
    return Series.objects.create(
        name='Test Series',
        sort_name='Test Series',
        year_began=1990,
        publication_dates='1990 - present',
        notes='',
        tracking_notes='',
        country=country,
        language=language,
        publisher=publisher,
    )


@pytest.fixture
def issue(db, series):
    """Return a saved ``Issue`` tied to ``series`` with ``sort_code=1``."""
    return Issue.objects.create(
        number='1',
        title='',
        volume='',
        isbn='',
        valid_isbn='',
        variant_name='',
        barcode='',
        publication_date='',
        key_date='',
        on_sale_date='',
        sort_code=1,
        indicia_frequency='',
        price='',
        editing='',
        notes='',
        indicia_printer_sourced_by='',
        series=series,
    )


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF ``APIClient``."""
    return APIClient()


@pytest.fixture
def authenticated_user(db, django_user_model):
    """Return a saved active user with a known password."""
    return django_user_model.objects.create_user(
        username='v2_test_user',
        password='v2_test_pass',
    )


@pytest.fixture
def authenticated_token(authenticated_user):
    """Return a ``Token`` bound to ``authenticated_user``."""
    token, _ = Token.objects.get_or_create(user=authenticated_user)
    return token


@pytest.fixture
def authenticated_client(api_client, authenticated_token):
    """Return an ``APIClient`` pre-configured with the test user's token."""
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Token {authenticated_token.key}',
    )
    return api_client
