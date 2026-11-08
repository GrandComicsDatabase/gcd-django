# -*- coding: utf-8 -*-
"""Tests of the covers when a variant is deleted, through the real views."""

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse

from apps.gcd.models import Cover
from apps.gcd.models.issue import VCS_Codes
from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.models import Changeset


def _submit_deletion(client, indexer, variant):
    """Submit the deletion of the variant and return its changeset."""
    indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(indexer)
    response = client.post(
      reverse('delete_revision', kwargs={'model_name': 'issue',
                                         'id': variant.id}),
      {'comments': 'Duplicate entry'})
    assert response.status_code == 302
    return Changeset.objects.get(issuerevisions__issue=variant,
                                 issuerevisions__deleted=True)


def _approve(client, changeset, country):
    """Assign the changeset to an editor, who approves it."""
    editor = User.objects.create_user('editor', password='editor')
    Indexer.objects.create(user=editor, country=country)
    editor.user_permissions.add(*Permission.objects.filter(
      codename__in=['can_reserve', 'can_approve'],
      content_type__app_label='indexer'))
    client.force_login(editor)
    for action in ('assign', 'approve'):
        response = client.post(
          reverse('process', kwargs={'id': changeset.id}),
          {action: action.title(), 'comments': ''})
        assert response.status_code == 302
    changeset.refresh_from_db()
    assert changeset.state == states.APPROVED


def _set_status(variant, status):
    """Set how the cover of the variant differs from its base."""
    variant.variant_cover_status = status
    variant.save()


@pytest.mark.django_db
def test_variant_with_the_image_of_its_base_keeps_the_base_covers(
        client, any_added_variant, any_indexer, any_country):
    _set_status(any_added_variant, VCS_Codes.NO_DIFFERENCE)
    base_cover = Cover.objects.create(issue=any_added_variant.variant_of)

    changeset = _submit_deletion(client, any_indexer, any_added_variant)
    _approve(client, changeset, any_country)

    any_added_variant.refresh_from_db()
    base_cover.refresh_from_db()
    assert any_added_variant.deleted is True
    assert base_cover.deleted is False
    assert not changeset.coverrevisions.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('status', [VCS_Codes.ONLY_SCAN_DIFFERENCE,
                                    VCS_Codes.ARTWORK_DIFFERENCE])
def test_variant_with_its_own_image_deletes_only_its_covers(
        client, any_added_variant, any_indexer, any_country, status):
    _set_status(any_added_variant, status)
    own_cover = Cover.objects.create(issue=any_added_variant)
    base_cover = Cover.objects.create(issue=any_added_variant.variant_of)

    changeset = _submit_deletion(client, any_indexer, any_added_variant)

    assert changeset.coverrevisions.get().cover == own_cover

    _approve(client, changeset, any_country)

    own_cover.refresh_from_db()
    base_cover.refresh_from_db()
    assert own_cover.deleted is True
    assert base_cover.deleted is False
