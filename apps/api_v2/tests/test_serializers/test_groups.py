# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the group serializer."""

from apps.api_v2.serializers.groups import GroupSerializer
from apps.gcd.models import (
    Character,
    Group,
    GroupMembership,
    GroupMembershipType,
    GroupNameDetail,
    Multiverse,
    Universe,
)
from apps.stddata.models import Language


def _create_multiverse(name):
    """Create a multiverse plus a hidden seed universe."""
    seed = Universe.objects.create(
        multiverse=name,
        name='Seed Universe',
        designation='Earth-0',
        year_first_published=1938,
        description='',
        notes='',
        deleted=True,
    )
    multiverse = Multiverse.objects.create(name=name, mainstream=seed)
    seed.verse = multiverse
    seed.save(update_fields=['verse'])
    return multiverse


def _create_language(code, name):
    """Create or return a language row for group tests."""
    obj, _created = Language.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def test_group_serializer_exposes_contract(db):
    """The group serializer emits the Sprint 2 group contract."""
    english = _create_language('en', 'English')
    marvel = _create_multiverse('Marvel')
    universe = Universe.objects.create(
        multiverse='Marvel',
        verse=marvel,
        name='Mainstream',
        designation='Earth-616',
        year_first_published=1961,
        description='',
        notes='',
    )
    group = Group.objects.create(
        name='Justice League',
        sort_name='Justice League',
        disambiguation='Silver Age',
        universe=universe,
        year_first_published=1960,
        language=english,
        description='Group description',
        notes='Group notes',
    )
    alias = GroupNameDetail.objects.create(
        name='JLA',
        sort_name='JLA',
        group=group,
        is_official_name=False,
    )
    official = GroupNameDetail.objects.create(
        name='Justice League',
        sort_name='Justice League',
        group=group,
        is_official_name=True,
    )
    batman = Character.objects.create(
        name='Batman',
        sort_name='Batman',
        disambiguation='',
        universe=universe,
        year_first_published=1939,
        language=english,
        description='',
        notes='',
    )
    superman = Character.objects.create(
        name='Superman',
        sort_name='Superman',
        disambiguation='',
        universe=universe,
        year_first_published=1938,
        language=english,
        description='',
        notes='',
    )
    member_type = GroupMembershipType.objects.create(
        type='member',
        reverse_type='belongs to',
    )
    GroupMembership.objects.create(
        character=superman,
        group=group,
        membership_type=member_type,
        notes='',
    )
    GroupMembership.objects.create(
        character=batman,
        group=group,
        membership_type=member_type,
        notes='',
    )
    group.keywords.add('alpha', 'beta')

    data = GroupSerializer(group).data

    assert set(data) == {
        'id',
        'name',
        'sort_name',
        'disambiguation',
        'year_first_published',
        'language',
        'universe',
        'description',
        'notes',
        'name_details',
        'members',
        'keywords',
        'created',
        'modified',
    }
    assert data['id'] == group.pk
    assert data['name'] == 'Justice League'
    assert data['sort_name'] == 'Justice League'
    assert data['disambiguation'] == 'Silver Age'
    assert data['year_first_published'] == 1960
    assert data['language'] == 'en'
    assert data['universe'] == {
        'id': universe.pk,
        'name': 'Marvel: Mainstream - Earth-616',
    }
    assert data['description'] == 'Group description'
    assert data['notes'] == 'Group notes'
    assert data['name_details'] == [
        {
            'id': alias.pk,
            'name': 'JLA',
            'sort_name': 'JLA',
            'is_official_name': False,
        },
        {
            'id': official.pk,
            'name': 'Justice League',
            'sort_name': 'Justice League',
            'is_official_name': True,
        },
    ]
    assert data['members'] == [
        {'id': batman.pk, 'name': 'Batman'},
        {'id': superman.pk, 'name': 'Superman'},
    ]
    assert set(data['keywords']) == {'alpha', 'beta'}
    assert data['created']
    assert data['modified']
