"""Tests for the development environment health endpoint."""

import pytest
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
