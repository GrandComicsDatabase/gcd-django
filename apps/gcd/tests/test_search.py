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

CREATOR = 'Search Person'

# The advanced-search field for each credit type. 'editing' is reached
# through story_editing; the rest share their name with the credit.
SEARCH_FIELD = {
    'script': 'script',
    'pencils': 'pencils',
    'inks': 'inks',
    'colors': 'colors',
    'letters': 'letters',
    'editing': 'story_editing',
}


def advanced_search(**fields):
    request = RequestFactory().get(
        '/search/advanced/process/',
        dict({'target': 'sequence', 'method': 'icontains'}, **fields))
    request.user = AnonymousUser()
    items, _target = do_advanced_search(request)
    return set(items.values_list('id', flat=True))


@pytest.fixture
def credited_stories(db):
    script = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    story_type = StoryType.objects.get_or_create(
        name='test-sequence', defaults={'sort_code': 99001})[0]
    country = Country.objects.get_or_create(
        id=902, defaults={'code': 'zs', 'name': 'Searchland'})[0]
    language = Language.objects.get_or_create(
        id=902, defaults={'code': 'zs', 'name': 'Searchish'})[0]
    publisher = Publisher.objects.create(
        name='Search Publisher', country=country, year_began=1950)
    series = Series.objects.create(
        name='Search Series', sort_name='Search Series', year_began=1950,
        country=country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1950')
    issue = Issue.objects.create(
        number='1', series=series, sort_code=0,
        publication_date='1950', key_date='1950-01-00')
    creator = Creator.objects.create(
        gcd_official_name=CREATOR, sort_name=CREATOR)
    name_detail = CreatorNameDetail.objects.create(
        name=CREATOR, creator=creator, in_script=script)

    # One story per credit type, all crediting the same person, so a
    # search that confuses two credit types returns a different story.
    stories = {}
    for name, type_id in CREDIT_TYPES.items():
        credit_type = CreditType.objects.get_or_create(
            id=type_id, defaults={'name': name, 'sort_code': type_id})[0]
        story = Story.objects.create(
            issue=issue, type=story_type, sequence_number=0)
        StoryCredit.objects.create(
            creator=name_detail, credit_type=credit_type, story=story)
        stories[name] = story
    return stories


@pytest.mark.parametrize('credit', sorted(SEARCH_FIELD))
def test_credit_search_matches_only_its_own_credit_type(credit,
                                                        credited_stories):
    matched = advanced_search(**{SEARCH_FIELD[credit]: CREATOR})

    assert matched == {credited_stories[credit].id}
