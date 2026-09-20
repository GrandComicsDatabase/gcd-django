# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Regression tests for the public API v2 OpenAPI contract."""

import json

import pytest
from django.test import override_settings
from drf_spectacular.validation import validate_schema

from apps.api_v2.tests.test_url_dispatch import _reload_v2_urlconf


@pytest.fixture
def restore_v2_urlconf():
    """Restore the default URL tree after schema tests reload it."""
    yield
    _reload_v2_urlconf()


def _schema(client):
    """Return the decoded public API v2 schema."""
    _reload_v2_urlconf()
    response = client.get('/api/v2/schema/', {'format': 'json'})
    assert response.status_code == 200
    return json.loads(response.content)


def _resolve_ref(schema, value):
    """Resolve a local component reference when ``value`` contains one."""
    reference = value.get('$ref')
    if reference is None:
        return value
    prefix = '#/components/schemas/'
    assert reference.startswith(prefix)
    return schema['components']['schemas'][reference.removeprefix(prefix)]


def _response_schema(schema, path, method='get', status='200'):
    """Return the JSON response schema for an operation."""
    return schema['paths'][path][method]['responses'][status]['content'][
        'application/json'
    ]['schema']


@pytest.mark.django_db
@override_settings(MYCOMICS=False)
def test_v2_schema_is_valid_openapi(client, restore_v2_urlconf):
    """The generated document validates against its declared OAS version."""
    schema = _schema(client)

    validate_schema(schema)


@pytest.mark.django_db
@override_settings(MYCOMICS=False)
def test_v2_schema_generation_has_no_warnings(
    client,
    restore_v2_urlconf,
    capsys,
):
    """Every custom response field has an explicit OpenAPI shape."""
    _schema(client)

    captured = capsys.readouterr()
    assert 'Warning [' not in captured.err


@pytest.mark.django_db
@override_settings(MYCOMICS=False)
def test_token_schema_separates_request_and_response(
    client,
    restore_v2_urlconf,
):
    """Swagger asks for credentials and returns a token separately."""
    schema = _schema(client)
    operation = schema['paths']['/api/v2/auth/token/']['post']

    request_schema = _resolve_ref(
        schema,
        operation['requestBody']['content']['application/json']['schema'],
    )
    response_schema = _resolve_ref(
        schema,
        _response_schema(schema, '/api/v2/auth/token/', method='post'),
    )

    assert set(request_schema['required']) == {'username', 'password'}
    assert set(request_schema['properties']) == {'username', 'password'}
    assert set(response_schema['required']) == {'token'}
    assert set(response_schema['properties']) == {'token'}


@pytest.mark.django_db
@override_settings(MYCOMICS=False)
def test_v2_schema_has_release_and_auth_metadata(
    client,
    restore_v2_urlconf,
):
    """The docs identify v2 and explain optional authentication and limits."""
    schema = _schema(client)
    description = ' '.join(schema['info']['description'].lower().split())

    assert schema['info']['version'] == '2.0.0'
    assert 'optional' in description
    assert '30 requests per hour' in description
    assert '2,000 requests per day' in description
    assert '/api/v2/auth/token/' in description


STRUCTURED_COMPONENT_FIELDS = {
    'BrandGroupList': {'parent': 'object'},
    'BrandGroup': {'emblems': 'array'},
    'BrandGroupReference': {'parent': 'object'},
    'BrandUse': {'publisher': 'object'},
    'Brand': {'groups': 'array', 'uses': 'array'},
    'Character': {
        'universe': 'object',
        'name_details': 'array',
        'group_memberships': 'array',
    },
    'CreatorList': {'birth_date': 'object', 'death_date': 'object'},
    'Creator': {
        'name_details': 'array',
        'signatures': 'array',
        'awards': 'array',
    },
    'FeatureList': {'feature_type': 'object'},
    'Feature': {'logos': 'array', 'relations': 'array'},
    'Group': {
        'universe': 'object',
        'name_details': 'array',
        'members': 'array',
    },
    'IndiciaPrinterList': {'parent': 'object'},
    'IndiciaPublisherList': {'parent': 'object'},
    'IssueStory': {
        'type': 'object',
        'script': 'array',
        'pencils': 'array',
        'inks': 'array',
        'colors': 'array',
        'letters': 'array',
        'editing': 'array',
    },
    'IssueList': {
        'series': 'object',
        'editing_credits': 'array',
        'indicia_publisher': 'object',
        'brand_emblems': 'array',
    },
    'IssueDetail': {'stories': 'array'},
    'Reprint': {
        'origin_story': 'object',
        'origin_issue': 'object',
        'target_story': 'object',
        'target_issue': 'object',
    },
    'SeriesList': {'publisher': 'object'},
    'Series': {'active_issue_ids': 'array'},
    'StoryList': {'type': 'object', 'issue': 'object'},
    'FeatureObject': {'feature_type': 'object'},
    'Story': {
        'feature_object': 'array',
        'feature_logo': 'array',
        'credits': 'array',
        'characters': 'array',
        'text_credits': 'object',
        'reprint_origins': 'array',
        'reprint_targets': 'array',
    },
    'StoryArc': {'stories': 'array', 'keywords': 'array'},
    'Universe': {'multiverse': 'object'},
}


@pytest.mark.django_db
@override_settings(MYCOMICS=False)
def test_v2_schema_documents_structured_response_fields(
    client,
    restore_v2_urlconf,
):
    """Nested objects and collections are not documented as strings."""
    schema = _schema(client)
    components = schema['components']['schemas']

    for component_name, expected_fields in STRUCTURED_COMPONENT_FIELDS.items():
        properties = components[component_name]['properties']
        for field_name, expected_type in expected_fields.items():
            field_schema = properties[field_name]
            if expected_type == 'object':
                assert '$ref' in field_schema or 'allOf' in field_schema
            else:
                assert field_schema['type'] == expected_type

    assert (
        components['IssueList']['properties']['variant_of']['nullable'] is True
    )


INTEGER_FILTERS = {
    '/api/v2/brand-groups/': {'parent'},
    '/api/v2/brands/': {'group', 'publisher'},
    '/api/v2/characters/': {'universe'},
    '/api/v2/features/': {'feature_type'},
    '/api/v2/groups/': {'universe'},
    '/api/v2/indicia-printers/': {'parent'},
    '/api/v2/indicia-publishers/': {'parent'},
    '/api/v2/issues/': {'series'},
    '/api/v2/reprints/': {
        'origin_issue',
        'origin_issue__series',
        'origin_story',
        'target_issue',
        'target_issue__series',
        'target_story',
    },
    '/api/v2/series/': {'publication_type', 'publisher'},
    '/api/v2/series-bonds/': {
        'bond_type',
        'origin',
        'origin_issue',
        'target',
        'target_issue',
    },
    '/api/v2/stories/': {'issue', 'issue__series', 'type'},
    '/api/v2/universes/': {'multiverse'},
}


@pytest.mark.django_db
@override_settings(MYCOMICS=False)
def test_v2_schema_documents_foreign_key_filters_as_integers(
    client,
    restore_v2_urlconf,
):
    """Database identifiers use integer query parameters in Swagger."""
    schema = _schema(client)

    for path, parameter_names in INTEGER_FILTERS.items():
        parameters = {
            parameter['name']: parameter
            for parameter in schema['paths'][path]['get']['parameters']
        }
        for parameter_name in parameter_names:
            assert parameters[parameter_name]['schema']['type'] == 'integer'
