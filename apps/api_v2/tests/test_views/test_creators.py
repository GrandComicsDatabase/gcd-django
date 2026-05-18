# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the creator v2 endpoints."""

from django.contrib.contenttypes.models import ContentType
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
    deleted=False,
):
    """Create a minimal creator row for view tests."""
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
        deleted=deleted,
    )


def test_creator_list_returns_paginated_results(api_client, db):
    """The list endpoint is anon-readable and paginated."""
    usa = _create_country('us', 'United States')
    creator = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='1926', month='09'),
        death_date=_create_date(year='2012', month='08', day='12'),
        birth_country=usa,
    )

    response = api_client.get(reverse('creator-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['next'] is None
    assert response.data['previous'] is None
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['id'] == creator.pk
    assert response.data['results'][0]['birth_country'] == 'us'
    assert response.data['results'][0]['birth_date'] == {
        'value': '1926-09',
        'precision': 'month',
        'year': 1926,
        'month': 9,
        'day': None,
        'year_uncertain': False,
        'month_uncertain': False,
        'day_uncertain': None,
    }
    assert 'keywords' not in response.data['results'][0]
    assert 'name_details' not in response.data['results'][0]
    assert 'signatures' not in response.data['results'][0]
    assert 'awards' not in response.data['results'][0]


def test_creator_list_handles_unknown_year_markers(api_client, db):
    """Legacy unknown-year date markers stay serializable on list responses."""
    creator = _create_creator(
        gcd_official_name='Mystery Creator',
        sort_name='Creator, Mystery',
        birth_date=_create_date(year='????'),
    )

    response = api_client.get(reverse('creator-list'))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == creator.pk
    assert response.data['results'][0]['birth_date'] == {
        'value': '????',
        'precision': 'year',
        'year': None,
        'month': None,
        'day': None,
        'year_uncertain': True,
        'month_uncertain': None,
        'day_uncertain': None,
    }


def test_creator_detail_returns_expected_payload(
    authenticated_client,
    db,
):
    """The detail endpoint returns the creator serializer payload."""
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
    signature = CreatorSignature.objects.create(
        name='WE',
        creator=creator,
        notes='Signature notes',
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

    response = authenticated_client.get(
        reverse('creator-detail', kwargs={'pk': creator.pk}),
    )

    assert response.status_code == 200
    assert response.data['id'] == creator.pk
    assert response.data['gcd_official_name'] == creator.gcd_official_name
    assert response.data['sort_name'] == creator.sort_name
    assert response.data['birth_country'] == 'us'
    assert response.data['birth_date'] == {
        'value': '1917',
        'precision': 'year',
        'year': 1917,
        'month': None,
        'day': None,
        'year_uncertain': False,
        'month_uncertain': None,
        'day_uncertain': None,
    }
    assert response.data['death_date'] is None
    assert response.data['name_details'] == [
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
    assert response.data['signatures'] == [
        {'id': signature.pk, 'name': 'WE'},
    ]
    assert response.data['awards'] == [
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
    assert 'keywords' not in response.data


def test_creator_list_applies_filter_query_params(
    authenticated_client,
    db,
):
    """The list endpoint applies django-filter query params."""
    usa = _create_country('us', 'United States')
    canada = _create_country('ca', 'Canada')
    matching = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        birth_date=_create_date(year='1926', month='09', day='18'),
        birth_country=usa,
    )
    _create_creator(
        gcd_official_name='Seth',
        sort_name='Seth',
        birth_date=_create_date(year='1962', month='09'),
        birth_country=canada,
    )

    response = authenticated_client.get(
        reverse('creator-list'),
        {
            'name': 'kub',
            'birth_country': 'us',
            'birth_date__gte': '1920',
            'birth_date__lte': '1930-12-31',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == matching.pk


def test_creator_list_filters_uncertain_partial_years(
    authenticated_client,
    db,
):
    """Bounded date filters keep uncertain year markers usable."""
    uncertain_match = _create_creator(
        gcd_official_name='Approximate Creator',
        sort_name='Approximate Creator',
        death_date=_create_date(year='200?'),
    )
    matching = _create_creator(
        gcd_official_name='Will Eisner',
        sort_name='Eisner, Will',
        death_date=_create_date(year='2005', month='01', day='03'),
    )
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
        death_date=_create_date(year='2012'),
    )

    response = authenticated_client.get(
        reverse('creator-list'),
        {
            'death_date__gte': '2000',
            'death_date__lte': '2009-12-31',
        },
    )

    assert response.status_code == 200
    assert response.data['count'] == 2
    assert [row['id'] for row in response.data['results']] == [
        uncertain_match.pk,
        matching.pk,
    ]


def test_creator_list_rejects_invalid_partial_date(
    authenticated_client,
    db,
):
    """Malformed partial-date values return a validation error."""
    response = authenticated_client.get(
        reverse('creator-list'),
        {'birth_date__gte': '1940-13'},
    )

    assert response.status_code == 400
    assert response.data == {
        'birth_date__gte': [
            'Enter a valid partial date in '
            'YYYY, YYYY-MM, or YYYY-MM-DD format.',
        ],
    }


def test_creator_endpoints_hide_soft_deleted_records(
    authenticated_client,
    db,
):
    """Soft-deleted creators disappear from list and detail responses."""
    visible = _create_creator(
        gcd_official_name='Visible Creator',
        sort_name='Visible Creator',
    )
    deleted = _create_creator(
        gcd_official_name='Deleted Creator',
        sort_name='Deleted Creator',
        deleted=True,
    )

    list_response = authenticated_client.get(reverse('creator-list'))
    detail_response = authenticated_client.get(
        reverse('creator-detail', kwargs={'pk': deleted.pk}),
    )

    assert list_response.status_code == 200
    assert list_response.data['count'] == 1
    assert list_response.data['results'][0]['id'] == visible.pk
    assert detail_response.status_code == 404


def test_creator_list_returns_304_for_if_modified_since(
    authenticated_client,
    db,
):
    """List responses support Last-Modified cache validation."""
    _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
    )

    response = authenticated_client.get(reverse('creator-list'))

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('creator-list'),
        HTTP_IF_MODIFIED_SINCE=response['Last-Modified'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''


def test_creator_detail_returns_304_for_if_none_match(
    authenticated_client,
    db,
):
    """Detail responses support ETag cache validation."""
    creator = _create_creator(
        gcd_official_name='Joe Kubert',
        sort_name='Kubert, Joe',
    )

    response = authenticated_client.get(
        reverse('creator-detail', kwargs={'pk': creator.pk}),
    )

    assert response.status_code == 200
    assert 'Last-Modified' in response
    assert 'ETag' in response

    cached_response = authenticated_client.get(
        reverse('creator-detail', kwargs={'pk': creator.pk}),
        HTTP_IF_NONE_MATCH=response['ETag'],
    )

    assert cached_response.status_code == 304
    assert cached_response.content == b''
