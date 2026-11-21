"""Tests for the deterministic local-development data command."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.core.management import call_command

from apps.gcd.models import (
    Character,
    Cover,
    Creator,
    Feature,
    Group,
    Image,
    Issue,
    Publisher,
    Reprint,
    Series,
    Story,
    StoryCharacter,
    StoryCredit,
    StoryGroup,
    Universe,
)
from apps.gcd.search_indexes import StoryIndex
from apps.gcd.management.commands.seed_development_data import (
    SAMPLE_RELATED_ROWS,
    SAMPLE_USERS,
)
from apps.indexer.models import Indexer
from apps.mycomics.models import Collection, Collector
from apps.oi import states
from apps.oi.models import ChangesetComment, SeriesRevision
from apps.stats.models import CountStats
from apps.stddata.models import Country, Language


def test_reserved_user_identities_match_the_loaded_fixture():
    fixture = (Path(__file__).resolve().parents[3] /
               'apps/indexer/fixtures/users.yaml')
    users = {
        row['pk']: row['fields']['username']
        for row in yaml.safe_load(fixture.read_text())
        if row['model'] == 'auth.user'
    }
    assert SAMPLE_USERS == users


def test_reserved_related_owners_match_the_loaded_fixture():
    fixture = (Path(__file__).resolve().parents[3] /
               'apps/indexer/fixtures/users.yaml')
    rows = yaml.safe_load(fixture.read_text())
    labels = {model._meta.label_lower for model, _, _ in SAMPLE_RELATED_ROWS}
    assert labels == {
        'indexer.indexer', 'mycomics.collector', 'mycomics.collection',
    }
    for model, owner_field, expected in SAMPLE_RELATED_ROWS:
        assert expected == {
            row['pk']: row['fields'][owner_field]
            for row in rows if row['model'] == model._meta.label_lower
        }


@pytest.mark.parametrize('user_id', [1, 2, 3, 4])
def test_seed_rejects_reserved_id_and_preserves_account_references(
        db, user_id):
    user = User.objects.create_user(
        pk=user_id, username=f'local-owner-{user_id}',
        password='local-password',
        email='local@example.invalid', is_staff=False, is_superuser=False,
    )
    profile = Indexer.objects.create(
        user=user, country=Country.objects.get(code='us'),
    )
    original_user = User.objects.values().get(pk=user.pk)
    original_profile = Indexer.objects.values().get(pk=profile.pk)
    with pytest.raises(CommandError, match='Refusing to overwrite'):
        call_command('seed_development_data')
    assert User.objects.values().get(pk=user.pk) == original_user
    assert Indexer.objects.values().get(pk=profile.pk) == original_profile
    assert User.objects.count() == 1
    assert not Series.objects.filter(name='[GCD DEV] Adventures').exists()


@pytest.mark.parametrize('username', [
    'admin', 'editor', 'dexter_1234', 'anon',
])
def test_seed_rejects_sample_username_owned_by_another_id(db, username):
    user = User.objects.create_user(
        pk=50, username=username, password='local-password',
    )
    original = User.objects.values().get(pk=user.pk)
    with pytest.raises(CommandError, match='Refusing to overwrite'):
        call_command('seed_development_data')
    assert User.objects.values().get(pk=user.pk) == original
    assert User.objects.count() == 1
    assert not Series.objects.filter(name='[GCD DEV] Adventures').exists()


def _account_rows():
    return {
        model._meta.label: list(model.objects.order_by('pk').values())
        for model in (User, Indexer, Collector, Collection)
    }


def _collector(user, pk):
    return Collector.objects.create(
        pk=pk, user=user, grade_system_id=1,
        default_language=Language.objects.get(code='en'),
    )


@pytest.mark.parametrize('model, reserved_id', [
    *[(Indexer, pk) for pk in range(1, 5)],
    *[(Collector, pk) for pk in range(1, 5)],
    *[(Collection, pk) for pk in (*range(1, 5), *range(101, 105))],
])
def test_seed_refuses_related_row_owned_by_a_nonreserved_user(
        db, model, reserved_id):
    user = User.objects.create_user(pk=50, username='local-owner')
    if model is Indexer:
        Indexer.objects.create(
            pk=reserved_id, user=user, country=Country.objects.get(code='us'),
            interests='Keep this profile', imps=123,
        )
    elif model is Collector:
        collector = _collector(user, reserved_id)
        collection = Collection.objects.create(
            pk=reserved_id, collector=collector, name='Keep this collection',
            description='Preserve this indirect user ownership',
        )
        collector.default_have_collection = collection
        collector.save(update_fields=['default_have_collection'])
    else:
        Collection.objects.create(
            pk=reserved_id, collector=_collector(user, 50),
            name='Keep this collection', description='Local work', public=True,
        )
    before = _account_rows()
    with patch(
        'apps.gcd.management.commands.seed_development_data.call_command',
        wraps=call_command,
    ) as loader:
        with pytest.raises(CommandError, match='Refusing to overwrite'):
            call_command('seed_development_data')
        loader.assert_not_called()
    assert _account_rows() == before
    assert not Series.objects.filter(name='[GCD DEV] Adventures').exists()


@pytest.mark.parametrize('model', [Indexer, Collector])
def test_seed_refuses_sample_one_to_one_owner_at_a_different_row_id(db, model):
    user = User.objects.create_user(pk=1, username='admin')
    if model is Indexer:
        Indexer.objects.create(
            pk=50, user=user, country=Country.objects.get(code='us'),
        )
    else:
        _collector(user, 50)
    before = _account_rows()
    with pytest.raises(CommandError, match='Refusing to overwrite'):
        call_command('seed_development_data')
    assert _account_rows() == before


def test_seed_preserves_unrelated_rows_outside_fixture_ids(db):
    user = User.objects.create_user(pk=50, username='local-owner')
    Indexer.objects.create(
        pk=50, user=user, country=Country.objects.get(code='us'), imps=123,
    )
    collector = _collector(user, 50)
    collection = Collection.objects.create(
        pk=50, collector=collector, name='Keep this collection',
        description='Local work', public=True,
    )
    collector.default_have_collection = collection
    collector.save(update_fields=['default_have_collection'])
    before = _account_rows()
    call_command('seed_development_data')
    call_command('seed_development_data')
    for model in (User, Indexer, Collector, Collection):
        assert list(model.objects.filter(pk=50).values()) == (
            before[model._meta.label]
        )


def test_seed_development_data_is_idempotent_and_initializes_stats(db):
    """Repeat setup preserves unrelated data and sample identities."""
    sentinel = Publisher.objects.create(
        name='Unrelated local publisher',
        notes='Keep this local work when refreshing the sample.',
        country=Country.objects.get(code='us'),
    )
    call_command('seed_development_data')

    custom_collection = Collection.objects.create(
        pk=50, collector=Collector.objects.get(pk=1),
        name='Keep this extra sample-owned collection',
    )
    original_collection = Collection.objects.values().get(pk=50)

    seeded_comment = ChangesetComment.objects.get(text__contains='[GCD DEV]')
    legacy_changeset = seeded_comment.changeset
    legacy_changeset.seriesrevisions.all().delete()
    legacy_changeset.approver = None
    legacy_changeset.save(update_fields=['approver'])

    seeded_story = Story.objects.get(title='[GCD DEV] First Flight Story')
    StoryGroup.objects.filter(story=seeded_story).delete()
    StoryCharacter.objects.filter(story=seeded_story).update(
        group_universe=None
    )

    call_command('seed_development_data')

    repaired_series = Series.objects.get(name='[GCD DEV] Adventures')
    repaired_revision = SeriesRevision.objects.get(
        changeset=legacy_changeset, series=repaired_series
    )
    assert repaired_revision.created == repaired_series.modified
    revision_created = repaired_revision.created

    call_command('seed_development_data')

    assert User.objects.filter(username='admin').count() == 1
    assert User.objects.filter(username='editor').count() == 1
    assert User.objects.filter(username='anon').count() == 1
    assert Indexer.objects.filter(user__username='admin').exists()
    assert CountStats.objects.filter(language=None, country=None).count() == 8

    publisher = Publisher.objects.get(name='[GCD DEV] Example Comics')
    series = Series.objects.get(
        name='[GCD DEV] Adventures', publisher=publisher,
    )
    issue = Issue.objects.get(series=series, sort_code=1)
    variant = Issue.objects.get(series=series, sort_code=2)
    story = Story.objects.get(issue=issue, sequence_number=0)

    assert variant.variant_of == issue
    assert Feature.objects.filter(name='[GCD DEV] Feature').exists()
    assert Creator.objects.filter(
        gcd_official_name='[GCD DEV] Alex Example',
    ).exists()
    assert StoryCredit.objects.filter(story=story).exists()
    assert Universe.objects.filter(designation='Earth-DEV').exists()
    assert Character.objects.filter(name='[GCD DEV] Captain Example').exists()
    assert Group.objects.filter(name='[GCD DEV] Example League').exists()
    assert StoryCharacter.objects.filter(story=story).exists()
    assert StoryGroup.objects.filter(story=story).count() == 1
    appearance = StoryCharacter.objects.get(story=story)
    assert appearance.group_universe == StoryGroup.objects.get(
        story=story
    ).universe
    prepared_story = StoryIndex().prepare(story)
    for field in ('characters', 'text'):
        assert '[GCD DEV] Captain Example' in prepared_story[field]
        assert '[GCD DEV] Example League' in prepared_story[field]
    assert Reprint.objects.filter(origin=story, target_issue=variant).exists()
    assert Cover.objects.filter(issue__in=(issue, variant)).count() == 2
    assert Image.objects.filter(object_id__in=(issue.id, variant.id)).exclude(
        image_file=''
    ).count() == 2
    comment = ChangesetComment.objects.get(text__contains='[GCD DEV]')
    changeset = comment.changeset
    assert changeset.state == states.APPROVED
    assert changeset.approver.username == 'admin'
    revision = SeriesRevision.objects.get(
        changeset=changeset, series=series
    )
    assert revision.created == revision_created
    sentinel.refresh_from_db()
    assert sentinel.name == 'Unrelated local publisher'
    assert sentinel.notes == 'Keep this local work when refreshing the sample.'
    assert Collection.objects.values().get(pk=custom_collection.pk) == (
        original_collection
    )
