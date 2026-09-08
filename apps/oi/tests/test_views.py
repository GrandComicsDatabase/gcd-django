import pytest

from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.indexer.models import Indexer


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('collapse_compare_view', 'url_suffix'),
    ((None, ''), (False, ''), (True, '?collapse=1')),
)
@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SITE_URL='https://www.example.com/',
)
def test_submit_email_uses_approver_compare_preference(
        client, any_country, any_indexer, any_added_publisher_rev,
        collapse_compare_view, url_suffix):
    approver = User.objects.create_user(
      'approver', email='approver@example.com', password='approver')
    if collapse_compare_view is not None:
        Indexer.objects.create(
          user=approver,
          country=any_country,
          collapse_compare_view=collapse_compare_view)

    changeset = any_added_publisher_rev.changeset
    changeset.approver = approver
    changeset.save()

    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)

    response = client.post(
      reverse('submit', kwargs={'id': changeset.id}),
      {'comments': ''})

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    compare_url = (
      f'https://www.example.com/changeset/{changeset.id}/compare/'
      f'{url_suffix}'
    )
    assert f'Please go to {compare_url} to compare the changes.' in (
      mail.outbox[0].body)
