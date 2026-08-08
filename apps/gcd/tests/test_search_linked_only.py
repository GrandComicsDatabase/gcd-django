# -*- coding: utf-8 -*-
import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.stddata.models import Country, Language, Script
from apps.gcd.models import (
    Publisher, Series, Issue, Story, StoryType, StoryCredit, CreditType,
)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.story import CREDIT_TYPES
from apps.gcd.views.search import do_advanced_search

PERSON = 'Test Person A'

# credit_is_linked values, exactly as the advanced-search dropdown sends them.
# A story credited only in a free-text field is matched by TEXT_CREDITS_ONLY
# and BOTH, but not by LINKED_ONLY (it has no linked credit record).
LINKED_ONLY = ''             # dropdown "linked credits only"
BOTH = 'True'                # dropdown "both linked and text credits"
TEXT_CREDITS_ONLY = 'False'  # dropdown "text credits only"

# Search field -> the story text field holding the same credit.
TEXT_FIELD = {
    'script': 'script',
    'pencils': 'pencils',
    'inks': 'inks',
    'colors': 'colors',
    'letters': 'letters',
    'story_editing': 'editing',
}


def advanced_search(**fields):
    request = RequestFactory().get(
        '/search/advanced/process/',
        dict({'target': 'sequence', 'method': 'icontains'}, **fields))
    request.user = AnonymousUser()
    items, _target = do_advanced_search(request)
    return set(items.values_list('id', flat=True))


@pytest.fixture
def issue(db):
    Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})
    country = Country.objects.get_or_create(
        id=907, defaults={'code': 'q3', 'name': 'Testland A'})[0]
    language = Language.objects.get_or_create(
        id=907, defaults={'code': 'q4', 'name': 'Testish A'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1965)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series',
        year_began=1965, country=country, language=language,
        publisher=publisher, is_comics_publication=True, has_gallery=False,
        publication_dates='1965')
    return Issue.objects.create(
        number='1', series=series, sort_code=0,
        publication_date='1965', key_date='1965-01-00')


@pytest.fixture
def story_type(db):
    return StoryType.objects.get_or_create(
        name='linked-only-sequence', defaults={'sort_code': 99010})[0]


def text_credited_story(issue, story_type, field):
    # Credited only in the free-text field: no StoryCredit object exists,
    # as is the case before a creator's credits are migrated.
    return Story.objects.create(
        issue=issue, type=story_type, sequence_number=0,
        **{TEXT_FIELD[field]: PERSON})


@pytest.mark.parametrize('field', sorted(TEXT_FIELD))
def test_linked_only_ignores_a_creator_with_no_linked_credit(field, issue,
                                                             story_type):
    text_credited_story(issue, story_type, field)

    matched = advanced_search(**{field: PERSON},
                              credit_is_linked=LINKED_ONLY)

    assert matched == set()


@pytest.mark.parametrize('credit_is_linked', [BOTH, TEXT_CREDITS_ONLY],
                         ids=['both', 'text_only'])
def test_text_credits_are_still_found_when_asked_for(credit_is_linked, issue,
                                                     story_type):
    story = text_credited_story(issue, story_type, 'script')

    matched = advanced_search(script=PERSON,
                              credit_is_linked=credit_is_linked)

    assert matched == {story.id}


def linked_credited_story(issue, story_type):
    creator = Creator.objects.create(
        gcd_official_name=PERSON, sort_name=PERSON)
    name = CreatorNameDetail.objects.create(
        name=PERSON, creator=creator,
        in_script=Script.objects.get(id=Script.LATIN_PK))
    linked = Story.objects.create(
        issue=issue, type=story_type, sequence_number=1)
    StoryCredit.objects.create(
        creator=name,
        credit_type=CreditType.objects.get_or_create(
            id=CREDIT_TYPES['script'],
            defaults={'name': 'script', 'sort_code': 1})[0],
        story=linked)
    return linked


def test_linked_only_still_finds_a_linked_credit(issue, story_type):
    linked = linked_credited_story(issue, story_type)

    matched = advanced_search(script=PERSON, credit_is_linked=LINKED_ONLY)

    assert matched == {linked.id}


def test_both_sources_require_every_linked_creator(issue, story_type):
    linked_credited_story(issue, story_type)

    matched = advanced_search(
        script='%s; Test Person Absent' % PERSON,
        credit_is_linked=BOTH)

    assert matched == set()
