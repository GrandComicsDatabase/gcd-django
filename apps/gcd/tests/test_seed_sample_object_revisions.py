"""The other sample objects have approved revisions, like objects saved
through the site, so they can be edited."""

import pytest

from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse

from apps.gcd.models import (
    Character,
    Creator,
    Feature,
    Group,
    Issue,
    Publisher,
    Reprint,
    Universe,
)
from apps.oi import states
from apps.oi.models import CTYPES, Changeset, ReprintRevision

SAMPLE_SERIES = '[GCD DEV] Adventures'


def _seed_and_log_in(client):
    """Seed the sample data and log in as its editor."""
    call_command('seed_development_data')
    client.force_login(User.objects.get(username='editor'))


@pytest.mark.django_db
@pytest.mark.parametrize('model_name, model, lookup', [
    ('publisher', Publisher, {'name': '[GCD DEV] Example Comics'}),
    ('creator', Creator, {'gcd_official_name': '[GCD DEV] Alex Example'}),
    ('feature', Feature, {'name': '[GCD DEV] Feature'}),
    ('universe', Universe, {'name': '[GCD DEV] Main Universe'}),
    ('character', Character, {'name': '[GCD DEV] Captain Example'}),
    ('group', Group, {'name': '[GCD DEV] Example League'}),
])
def test_a_sample_object_can_be_edited(client, model_name, model, lookup):
    _seed_and_log_in(client)
    data_object = model.objects.get(**lookup)

    response = client.post(reverse('reserve_revision', kwargs={
      'model_name': model_name, 'id': data_object.id}), follow=True)

    changeset = data_object.revisions.get(
      changeset__state=states.OPEN).changeset
    assert response.redirect_chain == [
      (reverse('edit', kwargs={'id': changeset.id}), 302)]
    assert response.status_code == 200


@pytest.mark.django_db
def test_the_sample_reprint_can_be_edited(client):
    _seed_and_log_in(client)
    variant = Issue.objects.get(series__name=SAMPLE_SERIES, sort_code=2)
    reprint = Reprint.objects.get(target_issue=variant)
    client.post(reverse('reserve_revision', kwargs={
      'model_name': 'issue', 'id': variant.id}))
    changeset = variant.revisions.get(changeset__state=states.OPEN).changeset

    response = client.post(reverse('reserve_reprint', kwargs={
      'reprint_id': reprint.id, 'changeset_id': changeset.id}),
      {'edit_note_target': 'Edit Note'}, follow=True)

    revision = ReprintRevision.objects.get(changeset=changeset)
    assert response.redirect_chain == [
      (reverse('edit_reprint', kwargs={'id': revision.id,
                                       'which_side': 'edit_note_target'}),
       302)]
    assert response.status_code == 200


@pytest.mark.django_db
def test_the_sample_changes_can_be_shown(client):
    _seed_and_log_in(client)

    for changeset in Changeset.objects.filter(state=states.APPROVED):
        response = client.get(reverse('compare', kwargs={'id': changeset.id}))
        assert response.status_code == 200


@pytest.mark.django_db
def test_seeding_again_adds_changesets_only_where_missing():
    call_command('seed_development_data')
    changesets = Changeset.objects.count()
    Changeset.objects.filter(change_type=CTYPES['creator']).delete()

    call_command('seed_development_data')

    assert Changeset.objects.count() == changesets
    creator = Creator.objects.get(gcd_official_name='[GCD DEV] Alex Example')
    assert creator.revisions.filter(
      changeset__state=states.APPROVED).count() == 1
