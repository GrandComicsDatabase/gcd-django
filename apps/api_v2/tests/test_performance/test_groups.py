# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for group endpoints."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

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


def _create_group(
    *,
    name,
    sort_name,
    year_first_published,
    language,
    universe=None,
):
    """Create a minimal group row for performance tests."""
    return Group.objects.create(
        name=name,
        sort_name=sort_name,
        disambiguation='',
        universe=universe,
        year_first_published=year_first_published,
        language=language,
        description='',
        notes='',
    )


def _populate_group_relationships(group, *, universe, language):
    """Attach related rows so the serializer exercises all prefetches."""
    GroupNameDetail.objects.create(
        name=f'{group.name} Official',
        sort_name=f'{group.sort_name} Official',
        group=group,
        is_official_name=True,
    )
    character = Character.objects.create(
        name=f'{group.name} Member',
        sort_name=f'{group.sort_name} Member',
        disambiguation='',
        universe=universe,
        year_first_published=group.year_first_published,
        language=language,
        description='',
        notes='',
    )
    member_type, _created = GroupMembershipType.objects.get_or_create(
        type='member',
        defaults={'reverse_type': 'belongs to'},
    )
    GroupMembership.objects.create(
        character=character,
        group=group,
        membership_type=member_type,
        notes='',
    )
    group.keywords.add(group.name.lower())


def test_group_list_query_count(api_client, db):
    """The group list stays on the expected query budget."""
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
    first = _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    second = _create_group(
        name='Legion of Super-Heroes',
        sort_name='Legion of Super-Heroes',
        year_first_published=1958,
        language=english,
        universe=universe,
    )
    _populate_group_relationships(
        first,
        universe=universe,
        language=english,
    )
    _populate_group_relationships(
        second,
        universe=universe,
        language=english,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('group-list'))

    assert response.status_code == 200
    assert len(context) == 6


def test_group_detail_query_count(api_client, db):
    """The group detail endpoint avoids lazy-loading regressions."""
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
    group = _create_group(
        name='Justice League',
        sort_name='Justice League',
        year_first_published=1960,
        language=english,
        universe=universe,
    )
    _populate_group_relationships(
        group,
        universe=universe,
        language=english,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('group-detail', kwargs={'pk': group.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 5
