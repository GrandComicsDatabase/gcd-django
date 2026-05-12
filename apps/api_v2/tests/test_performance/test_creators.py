# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Performance tests for creator endpoints."""

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import (
    Award,
    Creator,
    CreatorNameDetail,
    CreatorSignature,
    ReceivedAward,
)
from apps.stddata.models import Country, Date, Script


def _create_country(code, name):
    """Create or return a country row for creator tests."""
    obj, _created = Country.objects.get_or_create(
        code=code,
        defaults={'name': name},
    )
    return obj


def _create_date(
    *,
    year='',
    month='',
    day='',
    year_uncertain=False,
    month_uncertain=False,
    day_uncertain=False,
):
    """Create a partial-date row for creator tests."""
    date = Date()
    date.set(
        year=year,
        month=month,
        day=day,
        year_uncertain=year_uncertain,
        month_uncertain=month_uncertain,
        day_uncertain=day_uncertain,
        empty=True,
    )
    date.save()
    return date


def _create_script():
    """Create or return the Latin script row for creator tests."""
    obj, _created = Script.objects.get_or_create(
        code='Latn',
        defaults={
            'id': Script.LATIN_PK,
            'number': 215,
            'name': 'Latin',
        },
    )
    return obj


def _create_creator(
    *,
    gcd_official_name,
    sort_name,
    birth_date=None,
    death_date=None,
    birth_country=None,
):
    """Create a minimal creator row for performance tests."""
    return Creator.objects.create(
        gcd_official_name=gcd_official_name,
        sort_name=sort_name,
        disambiguation='',
        birth_date=birth_date,
        death_date=death_date,
        birth_country=birth_country,
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )


def _populate_creator_relationships(creator):
    """Attach related rows so the detail serializer hits all prefetches."""
    script = _create_script()
    CreatorNameDetail.objects.create(
        name=creator.gcd_official_name,
        sort_name=creator.sort_name,
        creator=creator,
        is_official_name=True,
        given_name='',
        family_name='',
        in_script=script,
    )
    CreatorSignature.objects.create(
        name=f'{creator.gcd_official_name} Sig',
        creator=creator,
        notes='',
    )
    award = Award.objects.create(
        name=f'{creator.gcd_official_name} Award',
        notes='',
    )
    content_type = ContentType.objects.get_for_model(Creator)
    ReceivedAward.objects.create(
        content_type=content_type,
        object_id=creator.pk,
        award=award,
        award_name='Best Creator',
        award_year=1989,
        notes='',
    )


def test_creator_list_query_count(api_client, db):
    """The creator list stays on the expected query budget."""
    usa = _create_country('us', 'United States')
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='1926', month='09', day='18'),
        birth_country=usa,
    )
    _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        birth_date=_create_date(year='1917'),
        birth_country=usa,
    )

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(reverse('creator-list'))

    assert response.status_code == 200
    assert len(context) == 3


def test_creator_detail_query_count(api_client, db):
    """The creator detail endpoint avoids lazy-loading regressions."""
    usa = _create_country('us', 'United States')
    creator = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='1926', month='09', day='18'),
        birth_country=usa,
    )
    _populate_creator_relationships(creator)

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(
            reverse('creator-detail', kwargs={'pk': creator.pk}),
        )

    assert response.status_code == 200
    assert len(context) == 5
