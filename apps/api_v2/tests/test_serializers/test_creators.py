# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the creator serializers."""

from django.contrib.contenttypes.models import ContentType

from apps.api_v2.serializers.creators import (
    CreatorListSerializer,
    CreatorSerializer,
)
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
    """Create a minimal creator row for serializer tests."""
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
        bio='Creator bio',
        notes='Creator notes',
    )


def test_creator_list_serializer_exposes_contract(db):
    """The creator list serializer emits the Sprint 2 list contract."""
    usa = _create_country('us', 'United States')
    creator = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(
            year='1926',
            month='09',
            year_uncertain=False,
            month_uncertain=True,
        ),
        death_date=_create_date(year='2012', month='08', day='12'),
        birth_country=usa,
    )

    data = CreatorListSerializer(creator).data

    assert set(data) == {
        'id',
        'gcd_official_name',
        'sort_name',
        'birth_date',
        'death_date',
        'birth_country',
        'bio',
        'notes',
        'created',
        'modified',
    }
    assert data['id'] == creator.pk
    assert data['gcd_official_name'] == 'Joe Kubert'
    assert data['sort_name'] == 'Kubert, Joe'
    assert data['birth_date'] == {
        'value': '1926-09?',
        'precision': 'month',
        'year': 1926,
        'month': 9,
        'day': None,
        'year_uncertain': False,
        'month_uncertain': True,
        'day_uncertain': None,
    }
    assert data['death_date'] == {
        'value': '2012-08-12',
        'precision': 'day',
        'year': 2012,
        'month': 8,
        'day': 12,
        'year_uncertain': False,
        'month_uncertain': False,
        'day_uncertain': False,
    }
    assert data['birth_country'] == 'us'
    assert data['bio'] == 'Creator bio'
    assert data['notes'] == 'Creator notes'
    assert data['created']
    assert data['modified']


def test_creator_detail_serializer_exposes_contract(db):
    """The creator detail serializer emits the Sprint 2 detail contract."""
    usa = _create_country('us', 'United States')
    script = _create_script()
    creator = _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        birth_date=_create_date(year='1917'),
        death_date=None,
        birth_country=usa,
    )
    alias = CreatorNameDetail.objects.create(
        name='William Erwin Eisner',
        sort_name='Eisner, William Erwin',
        creator=creator,
        is_official_name=False,
        given_name='William',
        family_name='Eisner',
        in_script=script,
    )
    official = CreatorNameDetail.objects.create(
        name='Will Eisner',
        sort_name='Eisner, Will',
        creator=creator,
        is_official_name=True,
        given_name='Will',
        family_name='Eisner',
        in_script=script,
    )
    CreatorNameDetail.objects.create(
        name='Deleted Alias',
        sort_name='ZZ Deleted Alias',
        creator=creator,
        is_official_name=False,
        given_name='Deleted',
        family_name='Alias',
        in_script=script,
        deleted=True,
    )
    signature = CreatorSignature.objects.create(
        name='WE',
        creator=creator,
        notes='Signature notes',
    )
    CreatorSignature.objects.create(
        name='Deleted Signature',
        creator=creator,
        notes='',
        deleted=True,
    )
    award = Award.objects.create(name='Eisner Awards', notes='')
    content_type = ContentType.objects.get_for_model(Creator)
    received_award = ReceivedAward.objects.create(
        content_type=content_type,
        object_id=creator.pk,
        award=award,
        award_name='Best Writer/Artist',
        award_year=1989,
        notes='Award notes',
    )
    ReceivedAward.objects.create(
        content_type=content_type,
        object_id=creator.pk,
        award=award,
        award_name='Deleted Award',
        award_year=1990,
        notes='',
        deleted=True,
    )

    data = CreatorSerializer(creator).data

    assert set(data) == {
        'id',
        'gcd_official_name',
        'sort_name',
        'birth_date',
        'death_date',
        'birth_country',
        'bio',
        'notes',
        'created',
        'modified',
        'name_details',
        'signatures',
        'awards',
    }
    assert data['birth_date'] == {
        'value': '1917',
        'precision': 'year',
        'year': 1917,
        'month': None,
        'day': None,
        'year_uncertain': False,
        'month_uncertain': None,
        'day_uncertain': None,
    }
    assert data['death_date'] is None
    assert data['name_details'] == [
        {
            'id': official.pk,
            'name': 'Will Eisner',
            'sort_name': 'Eisner, Will',
            'is_official_name': True,
        },
        {
            'id': alias.pk,
            'name': 'William Erwin Eisner',
            'sort_name': 'Eisner, William Erwin',
            'is_official_name': False,
        },
    ]
    assert data['signatures'] == [
        {'id': signature.pk, 'name': 'WE'},
    ]
    assert data['awards'] == [
        {
            'id': received_award.pk,
            'award': {
                'id': award.pk,
                'name': 'Eisner Awards',
            },
            'name': 'Best Writer/Artist',
            'year': 1989,
        },
    ]
