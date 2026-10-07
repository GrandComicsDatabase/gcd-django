# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Contract tests for paginated native Story Arc member issues."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.api_v2.serializers.issues import IssueListSerializer
from apps.api_v2.tests.test_views.test_story_arcs import (
    _create_story,
    _create_story_arc,
)
from apps.api_v2.throttling import (
    V2AnonRateThrottle,
    V2TokenUserRateThrottle,
)
from apps.api_v2.views.issues import IssueViewSet
from apps.gcd.models import Issue, Series


def _issue(series, *, number='1', sort_code=1, **kwargs):
    """Create an issue retaining the supplied native parent and facts."""
    return Issue.objects.create(
        series=series,
        number=number,
        sort_code=sort_code,
        key_date=kwargs.pop('key_date', '2024-01-01'),
        on_sale_date=kwargs.pop('on_sale_date', '2024-01-08'),
        **kwargs,
    )


def _series(original, *, name='Other Series', **kwargs):
    """Create another parent without changing the existing fixture."""
    return Series.objects.create(
        name=name,
        sort_name=name,
        year_began=1990,
        country=original.country,
        language=original.language,
        publisher=original.publisher,
        **kwargs,
    )


def _member(arc, issue, *, sequence_number=1):
    """Associate a story with an arc without inventing a global position."""
    story = _create_story(
        issue,
        title='Member story',
        sequence_number=sequence_number,
    )
    story.story_arc.add(arc)
    return story


def _url(arc):
    """Use the public path so an absent route fails as a 404 assertion."""
    return f'/api/v2/story-arcs/{arc.pk}/issues/'


def test_arc_issues_reuses_native_issue_list_payload(
    api_client,
    issue,
    language,
):
    """A member carries its real issue, parent, number, and variant facts."""
    arc = _create_story_arc(language)
    _member(arc, issue)
    _member(arc, issue, sequence_number=2)

    response = api_client.get(_url(arc))

    assert response.status_code == 200
    assert response.data['count'] == 1
    expected = IssueViewSet.queryset.filter(pk=issue.pk)
    assert (
        response.data['results']
        == IssueListSerializer(
            expected,
            many=True,
        ).data
    )
    assert response.data['results'][0]['series']['id'] == issue.series_id


def test_arc_issues_pages_are_distinct_and_stable(
    api_client,
    series,
    language,
):
    """Multiple stories cannot duplicate issues or alter page boundaries."""
    arc = _create_story_arc(language)
    members = [_issue(series, number=str(i), sort_code=i) for i in range(5)]
    for i, issue in enumerate(members):
        _member(arc, issue, sequence_number=10 - i)
        _member(arc, issue, sequence_number=20 - i)

    pages = []
    for page in (1, 2, 3):
        response = api_client.get(_url(arc), {'page': page, 'page_size': 2})
        assert response.status_code == 200
        assert response.data['count'] == 5
        pages.append([row['id'] for row in response.data['results']])
        repeated = api_client.get(_url(arc), {'page': page, 'page_size': 2})
        assert repeated.data == response.data
        assert bool(response.data['next']) == (page < 3)
        assert bool(response.data['previous']) == (page > 1)
    assert [pk for page in pages for pk in page] == [i.pk for i in members]


def test_arc_issues_publication_order_is_not_story_sequence(
    api_client,
    series,
    language,
):
    """Publication facts, parent sort name, sort code, and ID order ties."""
    arc = _create_story_arc(language)
    alpha = _series(series, name='Alpha')
    later = _issue(alpha, sort_code=3, key_date='2025-01-01')
    later_sale = _issue(alpha, sort_code=4, on_sale_date='2024-01-09')
    parent_after = _issue(series)
    sort_after = _issue(alpha, sort_code=2)
    first = _issue(alpha)
    tie = _issue(_series(series, name='Alpha'))
    for position, member in enumerate(
        [later, later_sale, parent_after, sort_after, tie, first],
        start=1,
    ):
        _member(arc, member, sequence_number=position)

    response = api_client.get(_url(arc))

    assert response.status_code == 200
    assert [row['id'] for row in response.data['results']] == [
        first.pk,
        tie.pk,
        sort_after.pk,
        parent_after.pk,
        later_sale.pk,
        later.pk,
    ]


def test_arc_issues_preserves_cross_series_variants(
    api_client,
    series,
    language,
):
    """Explicit variants remain exact members, never base substitutions."""
    arc = _create_story_arc(language)
    base = _issue(series)
    variant_parent = _series(series)
    variant = _issue(variant_parent, number='1/A', variant_of=base)
    _member(arc, variant)

    response = api_client.get(_url(arc))

    assert response.status_code == 200
    assert response.data['count'] == 1
    row = response.data['results'][0]
    assert (row['id'], row['series']['id'], row['number']) == (
        variant.pk,
        variant_parent.pk,
        '1/A',
    )
    assert row['variant_of'] == base.pk


@pytest.mark.parametrize('deleted_model', ['story', 'issue', 'series'])
def test_arc_issues_hides_deleted_members(
    api_client,
    issue,
    language,
    deleted_model,
):
    """A public page excludes deleted stories, issues, and parents."""
    arc = _create_story_arc(language)
    story = _member(arc, issue)
    target = {'story': story, 'issue': issue, 'series': issue.series}[
        deleted_model
    ]
    target.deleted = True
    target.save(update_fields=['deleted'])

    response = api_client.get(_url(arc))

    assert response.status_code == 200
    assert response.data == {
        'count': 0,
        'next': None,
        'previous': None,
        'results': [],
    }


def test_arc_issues_excludes_other_arcs_and_accepts_empty_arc(
    api_client,
    issue,
    language,
):
    """An existing empty arc is 200, not a lookup of another arc's files."""
    empty = _create_story_arc(language)
    other = _create_story_arc(language, name='Other Arc')
    _member(other, issue)

    response = api_client.get(_url(empty))

    assert response.status_code == 200
    assert response.data['count'] == 0
    assert response.data['results'] == []


@pytest.mark.django_db(transaction=True)
def test_arc_issues_missing_or_deleted_arc_is_not_found(
    api_client,
    language,
):
    """Deleted and nonexistent parents both retain normal 404 behavior."""
    arc = _create_story_arc(language, deleted=True)
    assert api_client.get(_url(arc)).status_code == 404
    missing = api_client.get('/api/v2/story-arcs/999999/issues/')
    assert missing.status_code == 404


def test_arc_issues_keeps_existing_page_size_bounds(
    api_client,
    series,
    language,
):
    """Default pages hold 50 issues and oversized requests cap at 200."""
    arc = _create_story_arc(language)
    for i in range(201):
        _member(arc, _issue(series, number=str(i), sort_code=i))

    default = api_client.get(_url(arc))
    oversized = api_client.get(_url(arc), {'page_size': 1000})

    assert default.status_code == oversized.status_code == 200
    assert default.data['count'] == oversized.data['count'] == 201
    assert len(default.data['results']) == 50
    assert len(oversized.data['results']) == 200
    assert oversized.data['next'] is not None


@pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
@pytest.mark.django_db(transaction=True)
def test_arc_issues_is_read_only(api_client, issue, language, method):
    """The additive endpoint cannot edit membership or native issues."""
    arc = _create_story_arc(language)
    story = _member(arc, issue)

    response = getattr(api_client, method)(_url(arc), {}, format='json')

    assert response.status_code == 405
    assert story.story_arc.filter(pk=arc.pk).exists()
    assert Issue.objects.filter(pk=issue.pk).exists()


@pytest.mark.parametrize(
    ('client_name', 'throttle'),
    [
        ('api_client', V2AnonRateThrottle),
        ('authenticated_client', V2TokenUserRateThrottle),
    ],
)
def test_arc_issues_inherits_v2_throttling(
    request,
    language,
    monkeypatch,
    client_name,
    throttle,
):
    """Anonymous and token readers retain 429 and Retry-After behavior."""
    client = request.getfixturevalue(client_name)
    arc = _create_story_arc(language)
    monkeypatch.setattr(throttle, 'rate', '1/minute')

    first = client.get(_url(arc))
    limited = client.get(_url(arc))

    assert first.status_code == 200
    assert limited.status_code == 429
    assert int(limited['Retry-After']) > 0


@pytest.mark.parametrize('member_count', [1, 25, 100])
def test_arc_issues_query_count_is_bounded(
    api_client,
    series,
    language,
    member_count,
):
    """The existing batched issue prefetches avoid per-member queries."""
    arc = _create_story_arc(language)
    for i in range(member_count):
        _member(arc, _issue(series, number=str(i), sort_code=i))

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(_url(arc), {'page_size': 100})

    assert response.status_code == 200
    assert len(response.data['results']) == member_count
    assert len(context) <= 10
