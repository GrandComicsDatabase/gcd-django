# -*- coding: utf-8 -*-
import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.stddata.models import Country, Language, Script
from apps.gcd.models import (
    Publisher, Series, Issue, Story, StoryType, StoryCredit, CreditType,
)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.gcd.models.issue import IssueCredit
from apps.gcd.models.story import CREDIT_TYPES
from apps.gcd.views.search import do_advanced_search, _linked_story_ids

CREATOR = 'Test Person A'

# credit_is_linked values, exactly as the advanced-search dropdown sends them.
# LINKED_ONLY matches only linked credit records, TEXT_CREDITS_ONLY only the
# free-text credit fields, and BOTH matches either.
LINKED_ONLY = ''             # dropdown "linked credits only"
BOTH = 'True'                # dropdown "both linked and text credits"
TEXT_CREDITS_ONLY = 'False'  # dropdown "text credits only"


def advanced_search(**fields):
    request = RequestFactory().get(
        '/search/advanced/process/',
        dict({'target': 'sequence', 'method': 'icontains'}, **fields))
    request.user = AnonymousUser()
    items, _target = do_advanced_search(request)
    return set(items.values_list('id', flat=True))


@pytest.fixture
def world(db):
    script = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    story_type = StoryType.objects.get_or_create(
        name='credit-sequence', defaults={'sort_code': 99003})[0]
    country = Country.objects.get_or_create(
        id=904, defaults={'code': 'q5', 'name': 'Testland C'})[0]
    language = Language.objects.get_or_create(
        id=904, defaults={'code': 'q6', 'name': 'Testish C'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1960)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series', year_began=1960,
        country=country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1960')
    creator = Creator.objects.create(
        gcd_official_name=CREATOR, sort_name=CREATOR)
    name = CreatorNameDetail.objects.create(
        name=CREATOR, creator=creator, in_script=script)
    return {'series': series, 'type': story_type, 'name': name}


def make_issue(world, number):
    return Issue.objects.create(
        number=number, series=world['series'], sort_code=int(number),
        publication_date='1960', key_date='1960-01-00')


@pytest.fixture
def linked_and_text(world):
    # One story credited through a StoryCredit object, one only in the
    # free-text field. The migration moves stories from the latter to the
    # former, so the two sources must stay distinguishable.
    issue = make_issue(world, '1')
    linked = Story.objects.create(
        issue=issue, type=world['type'], sequence_number=0)
    StoryCredit.objects.create(
        creator=world['name'],
        credit_type=CreditType.objects.get_or_create(
            id=CREDIT_TYPES['script'],
            defaults={'name': 'script', 'sort_code': 1})[0],
        story=linked)
    text = Story.objects.create(
        issue=issue, type=world['type'], sequence_number=1, script=CREATOR)
    return {'linked': linked, 'text': text}


@pytest.mark.parametrize('credit_is_linked,expected', [
    (LINKED_ONLY, ['linked']),
    (BOTH, ['linked', 'text']),
    (TEXT_CREDITS_ONLY, ['text']),
], ids=['linked_only', 'both', 'text_only'])
def test_credit_is_linked_picks_the_credit_source(credit_is_linked, expected,
                                                  linked_and_text):
    matched = advanced_search(script=CREATOR,
                              credit_is_linked=credit_is_linked)

    assert matched == {linked_and_text[k].id for k in expected}


def test_linked_story_ids_materializes_the_creator_ids(linked_and_text):
    # Creator ids must be materialized before the story lookup; a lazy
    # queryset becomes IN (subquery), which MySQL optimizes poorly. See
    # https://docs.djangoproject.com/en/5.2/ref/models/querysets/#nested-queries-performance
    with CaptureQueriesContext(connection) as ctx:
        stories = _linked_story_ids(CREATOR, 'script', 'icontains')

    assert stories == [linked_and_text['linked'].id]
    queries = [q['sql'] for q in ctx.captured_queries]
    assert len(queries) == 2
    # Ids appear as literals in the story query, not as a nested subquery.
    assert 'creator_name_detail' in queries[0]
    assert 'creator_name_detail' not in queries[1]


def test_issue_editing_matches_stories_of_the_edited_issue(world):
    edited = make_issue(world, '1')
    other = make_issue(world, '2')
    IssueCredit.objects.create(
        creator=world['name'],
        credit_type=CreditType.objects.get_or_create(
            id=CREDIT_TYPES['editing'],
            defaults={'name': 'editing', 'sort_code': 6})[0],
        issue=edited)
    wanted = Story.objects.create(
        issue=edited, type=world['type'], sequence_number=0)
    Story.objects.create(issue=other, type=world['type'], sequence_number=0)

    assert advanced_search(issue_editing=CREATOR) == {wanted.id}


def test_story_editing_and_issue_editing_are_separate_credits(world):
    story_credit_issue = make_issue(world, '1')
    issue_credit_issue = make_issue(world, '2')
    editing_type = CreditType.objects.get_or_create(
        id=CREDIT_TYPES['editing'], defaults={'name': 'editing',
                                              'sort_code': 6})[0]
    story_edited = Story.objects.create(
        issue=story_credit_issue, type=world['type'], sequence_number=0)
    issue_edited = Story.objects.create(
        issue=issue_credit_issue, type=world['type'], sequence_number=0)
    StoryCredit.objects.create(
        creator=world['name'], credit_type=editing_type, story=story_edited)
    IssueCredit.objects.create(
        creator=world['name'], credit_type=editing_type,
        issue=issue_credit_issue)

    assert advanced_search(story_editing=CREATOR) == {story_edited.id}
    assert advanced_search(issue_editing=CREATOR) == {issue_edited.id}
