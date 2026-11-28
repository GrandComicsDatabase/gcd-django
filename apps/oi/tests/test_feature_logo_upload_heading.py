# -*- coding: utf-8 -*-
"""Tests of the page to upload the image of a feature logo."""

import pytest

from django.urls import reverse

from apps.gcd.models import FeatureLogo, ImageType


@pytest.fixture
def upload_url(client, any_indexer):
    """Log in an indexer and return the upload URL of a feature logo."""
    ImageType.objects.get_or_create(
      name='FeatureLogo', defaults={'description': 'Feature Logo'})
    logo = FeatureLogo.objects.create(name='Some Logo',
                                      sort_name='Some Logo', notes='')
    client.force_login(any_indexer)
    return reverse('upload_image',
                   kwargs={'model_name': 'feature_logo', 'id': logo.id,
                           'image_type': 'FeatureLogo'})


@pytest.mark.django_db
def test_upload_page_shows_heading_and_guidelines(client, upload_url):
    response = client.get(upload_url)

    assert response.status_code == 200
    page = response.content.decode()
    assert 'scan of the feature logo' in page
    assert 'Please only upload an image of the feature logo.' in page
