# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for v2 credit serialization helpers."""

from decimal import Decimal

from apps.api_v2.utils.credits import (
    collect_credit_strings,
    collect_story_credit_entries,
)
from apps.gcd.models import (
    CREDIT_TYPES,
    Creator,
    CreatorNameDetail,
    CreditType,
    Story,
    StoryCredit,
    StoryType,
)
from apps.stddata.models import Script


def _create_script():
    """Return a Latin script row fit for creator-name fixtures."""
    obj, _ = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={
            'number': 215,
            'name': 'Latin',
        },
    )
    return obj


def _create_creator(name, sort_name):
    """Return a creator plus official name-detail row."""
    creator = Creator.objects.create(
        gcd_official_name=name,
        sort_name=sort_name,
        disambiguation='',
        birth_province='',
        birth_city='',
        death_province='',
        death_city='',
        bio='',
        notes='',
    )
    name_detail = CreatorNameDetail.objects.create(
        creator=creator,
        name=name,
        sort_name=sort_name,
        is_official_name=True,
        given_name='',
        family_name='',
        in_script=_create_script(),
    )
    return creator, name_detail


def _create_credit_type(name, sort_code):
    """Return a credit type with the canonical v2 test id."""
    credit_type, _ = CreditType.objects.update_or_create(
        id=CREDIT_TYPES[name],
        defaults={
            'name': name,
            'sort_code': sort_code,
        },
    )
    return credit_type


def _create_story(issue):
    """Return a story row suitable for credit helper tests."""
    story_type, _ = StoryType.objects.get_or_create(
        name='Comic Story',
        defaults={'sort_code': 19},
    )
    return Story.objects.create(
        title='Lead Story',
        feature='Feature Text',
        sequence_number=1,
        page_count=Decimal('10.000'),
        script='Legacy Writer One; Legacy Writer Two',
        pencils='',
        inks='',
        colors='',
        letters='',
        editing='',
        job_number='',
        genre='',
        characters='',
        synopsis='',
        reprint_notes='',
        notes='',
        issue=issue,
        type=story_type,
    )


def test_collect_credit_strings_keeps_existing_plain_text_contract(issue):
    """The existing issue helper still returns normalized and legacy names."""
    story = _create_story(issue)
    writer, writer_name = _create_creator('Writer One', 'Writer, One')
    script_type = _create_credit_type('script', 1)
    credit = StoryCredit.objects.create(
        creator=writer_name,
        credit_type=script_type,
        story=story,
        signed_as='',
        credited_as='',
        sourced_by='',
        credit_name='',
    )
    story.active_credit_list = [credit]

    assert writer.pk == writer_name.creator_id
    assert collect_credit_strings(
        story,
        'script',
        prefetched_attr='active_credit_list',
    ) == [
        'Writer One',
        'Legacy Writer One',
        'Legacy Writer Two',
    ]


def test_collect_story_credit_entries_returns_structured_credit_shape(issue):
    """Structured credits expose creator id/name plus role only."""
    story = _create_story(issue)
    writer, writer_name = _create_creator('Writer One', 'Writer, One')
    penciler, penciler_name = _create_creator(
        'Penciler One',
        'Penciler, One',
    )
    deleted_creator, deleted_name = _create_creator(
        'Deleted Writer',
        'Writer, Deleted',
    )
    script_type = _create_credit_type('script', 1)
    pencils_type = _create_credit_type('pencils', 2)
    deleted_credit = StoryCredit.objects.create(
        creator=deleted_name,
        credit_type=script_type,
        story=story,
        signed_as='',
        credited_as='',
        sourced_by='',
        credit_name='',
        deleted=True,
    )
    pencils_credit = StoryCredit.objects.create(
        creator=penciler_name,
        credit_type=pencils_type,
        story=story,
        signed_as='',
        credited_as='',
        sourced_by='',
        credit_name='',
    )
    script_credit = StoryCredit.objects.create(
        creator=writer_name,
        credit_type=script_type,
        story=story,
        signed_as='',
        credited_as='',
        sourced_by='',
        credit_name='',
    )
    story.active_credit_list = [
        deleted_credit,
        pencils_credit,
        script_credit,
    ]

    assert collect_story_credit_entries(
        story,
        prefetched_attr='active_credit_list',
    ) == [
        {
            'creator': {
                'id': writer.pk,
                'name': 'Writer One',
            },
            'role': 'script',
        },
        {
            'creator': {
                'id': penciler.pk,
                'name': 'Penciler One',
            },
            'role': 'pencils',
        },
    ]
    assert deleted_creator.pk == deleted_name.creator_id


def test_collect_story_credit_entries_ignores_legacy_text(issue):
    """Legacy text has no creator id, so it is not structured credit data."""
    story = _create_story(issue)
    story.active_credit_list = []

    assert (
        collect_story_credit_entries(
            story,
            prefetched_attr='active_credit_list',
        )
        == []
    )
