"""Tests for the development environment health endpoint."""

import json
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.gcd.views.health import health


@pytest.mark.django_db
def test_health_check_confirms_database_connection(django_assert_num_queries):
    """The health endpoint checks the database without loading catalog data."""
    health_url = reverse('health')

    assert resolve(health_url).func is health

    with django_assert_num_queries(1):
        response = health(RequestFactory().get(health_url))

    assert response.status_code == 200
    assert response.content == b'{"status": "ok"}'


@pytest.mark.django_db
def test_health_check_stays_lightweight_through_middleware(
        client, django_assert_num_queries):
    """A complete health request adds only the transaction wrapper."""
    with django_assert_num_queries(3):
        response = client.get(reverse('health'))

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_health_check_handles_database_failure():
    """Database failures return a small response instead of a debug page."""
    request = RequestFactory().get(reverse('health'))

    with patch('apps.gcd.views.health.connection.cursor',
               side_effect=DatabaseError('Connection refused')):
        response = health(request)

    assert response.status_code == 503
    assert json.loads(response.content) == {'status': 'error'}
