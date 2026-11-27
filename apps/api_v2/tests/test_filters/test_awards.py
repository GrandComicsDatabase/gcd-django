# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for Award and received-award filter sets."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.api_v2.filters.awards import (
    AwardFilterSet,
    AwardRecipientFilterSet,
)
from apps.gcd.models import Award, Creator, ReceivedAward

pytestmark = pytest.mark.django_db


def _create_creator(name):
    """Create a minimal Creator recipient."""
    return Creator.objects.create(
        gcd_official_name=name,
        sort_name=name,
        disambiguation='',
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )


def _create_received_award(*, award, recipient, year):
    """Create a received Award for ``recipient``."""
    return ReceivedAward.objects.create(
        content_type=ContentType.objects.get_for_model(recipient),
        object_id=recipient.pk,
        award=award,
        award_name='Best Work',
        award_year=year,
        notes='',
    )


def test_award_filter_matches_name_icontains():
    """The Award name filter uses case-insensitive containment."""
    matching = Award.objects.create(name='Eisner Awards', notes='')
    Award.objects.create(name='Harvey Awards', notes='')

    queryset = AwardFilterSet(
        {'name': 'EISNER'},
        queryset=Award.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_award_filter_matches_modified_range():
    """Award timestamp filters support delta-style queries."""
    older = Award.objects.create(name='Older Award', notes='')
    newer = Award.objects.create(name='Newer Award', notes='')
    now = timezone.now()
    Award.objects.filter(pk=older.pk).update(modified=now - timedelta(days=2))
    Award.objects.filter(pk=newer.pk).update(modified=now - timedelta(hours=1))

    queryset = AwardFilterSet(
        {'modified__gt': (now - timedelta(days=1)).isoformat()},
        queryset=Award.objects.all(),
    ).qs

    assert list(queryset) == [newer]


def test_award_recipient_filter_matches_type_and_year():
    """Recipient type and Award year filters combine exactly."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    creator = _create_creator('Test Creator')
    matching = _create_received_award(
        award=award,
        recipient=creator,
        year=1989,
    )
    _create_received_award(
        award=award,
        recipient=creator,
        year=1990,
    )

    queryset = AwardRecipientFilterSet(
        {
            'recipient_type': 'creator',
            'award_year': '1989',
        },
        queryset=ReceivedAward.objects.all(),
    ).qs

    assert list(queryset) == [matching]


def test_award_recipient_filter_matches_created_range():
    """Received Award timestamp ranges support bounded queries."""
    award = Award.objects.create(name='Eisner Awards', notes='')
    creator = _create_creator('Test Creator')
    older = _create_received_award(
        award=award,
        recipient=creator,
        year=1989,
    )
    newer = _create_received_award(
        award=award,
        recipient=creator,
        year=1990,
    )
    now = timezone.now()
    ReceivedAward.objects.filter(pk=older.pk).update(
        created=now - timedelta(days=2),
    )
    ReceivedAward.objects.filter(pk=newer.pk).update(
        created=now - timedelta(hours=1),
    )

    queryset = AwardRecipientFilterSet(
        {'created__lte': (now - timedelta(days=1)).isoformat()},
        queryset=ReceivedAward.objects.all(),
    ).qs

    assert list(queryset) == [older]
