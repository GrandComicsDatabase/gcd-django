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

CREATOR = 'Test Person A'

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
        id=902, defaults={'code': 'zs', 'name': 'Testland B'})[0]
    language = Language.objects.get_or_create(
        id=902, defaults={'code': 'zs', 'name': 'Testish B'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1950)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series', year_began=1950,
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


@pytest.fixture
def variant_issues(credited_stories):
    """A named base issue with a named variant, and an unnamed plain issue."""
    base = next(iter(credited_stories.values())).issue
    Issue.objects.filter(id=base.id).update(variant_name='Regular')
    variant = Issue.objects.create(
        number='2', series=base.series, sort_code=1, variant_of=base,
        variant_name='Virgin')
    plain = Issue.objects.create(number='3', series=base.series, sort_code=2,
                                 notes='plain note')
    # a deleted variant counts neither as an issue nor as a variant of plain
    Issue.objects.create(number='4', series=base.series, sort_code=3,
                         variant_of=plain, variant_name='Gone', deleted=True)
    return {'base': base, 'variant': variant, 'plain': plain}


def test_variant_fields_from_the_rendered_page(client, variant_issues):
    """The page has both fields; submitting them gives a result page."""
    page = client.get('/search/advanced/').content.decode()
    assert '<select name="has_variant_name"' in page
    assert '<select name="has_variants"' in page
    assert 'Has a Variant Name' in page and 'Has Variants' in page

    response = client.get('/search/advanced/process/', {
        'target': 'issue', 'method': 'icontains',
        'has_variant_name': 'True', 'has_variants': 'True'})

    assert response.status_code == 200
    assert variant_issues['base'].get_absolute_url() in str(response.content)


@pytest.mark.parametrize('fields, expected', [
    ({'has_variant_name': 'True'}, {'base', 'variant'}),
    ({'has_variant_name': 'False'}, {'plain'}),
    ({'has_variants': 'True'}, {'base'}),
    ({'has_variants': 'False'}, {'variant', 'plain'}),
    # with Is a Variant they tell the kinds of base issue apart
    ({'is_variant': 'False', 'has_variant_name': 'False'}, {'plain'}),
    ({'is_variant': 'False', 'has_variants': 'True'}, {'base'}),
    # the OR behavior applies as to the other issue fields
    ({'logic': 'True', 'has_variant_name': 'False', 'has_variants': 'True'},
     {'base', 'plain'}),
])
def test_variant_fields_find_their_issues(variant_issues, fields, expected):
    """Each answer finds its issues; deleted variants do not count."""
    assert advanced_search(target='issue', **fields) == {
        variant_issues[name].id for name in expected}


def test_variant_fields_on_a_publisher_concern_single_issues(variant_issues):
    """One named issue is enough, and the fields are about the same issue."""
    publisher_id = variant_issues['base'].series.publisher_id

    assert advanced_search(target='publisher',
                           has_variant_name='True') == {publisher_id}
    assert advanced_search(target='publisher', has_variants='True',
                           issue_notes='plain note') == set()
    assert advanced_search(target='publisher', has_variants='True',
                           issues='1') == {publisher_id}


@pytest.mark.parametrize('target', [
    'issue', 'sequence', 'cover', 'issue_cover', 'series', 'publisher',
    'brand_group', 'brand_emblem', 'indicia_publisher'])
def test_variant_fields_on_every_search_target(variant_issues, target):
    """Every kind of search finds what belongs to the matching issue."""
    base = variant_issues['base']
    publisher = base.series.publisher
    group = publisher.brandgroup_set.create(name='Group')
    brand = group.brand_set.create(name='Emblem')
    indicia = publisher.indiciapublisher_set.create(
        name='Indicia', country=publisher.country)
    base.brand_emblem.add(brand)
    Issue.objects.filter(id=base.id).update(indicia_publisher=indicia)
    cover = base.cover_set.create()
    variant_issues['plain'].cover_set.create()
    expected = {'issue': {base.id}, 'cover': {cover.id},
                'sequence': set(base.story_set.values_list('id', flat=True)),
                'issue_cover': {cover.id}, 'series': {base.series_id},
                'publisher': {publisher.id}, 'brand_group': {group.id},
                'brand_emblem': {brand.id}, 'indicia_publisher': {indicia.id}}

    assert advanced_search(target=target, has_variant_name='True',
                           has_variants='True') == expected[target]
    assert advanced_search(target=target, has_variants='True',
                           has_variant_name='False') == set()


@pytest.mark.parametrize('credit', sorted(SEARCH_FIELD))
def test_credit_search_matches_only_its_own_credit_type(credit,
                                                        credited_stories):
    matched = advanced_search(**{SEARCH_FIELD[credit]: CREATOR})

    assert matched == {credited_stories[credit].id}


def test_credit_search_ignores_deleted_credits(credited_stories):
    StoryCredit.objects.filter(
        story=credited_stories['inks']).update(deleted=True)

    assert advanced_search(inks=CREATOR) == set()


@pytest.mark.parametrize('credit', sorted(SEARCH_FIELD))
def test_semicolon_separated_creators_must_all_be_credited(
        credit, credited_stories):
    # 'A; B' means stories credited to both A and B, not either of them.
    solo = credited_stories[credit]
    shared = Story.objects.create(
        issue=solo.issue, type=solo.type, sequence_number=1)
    credit_type = CreditType.objects.get(id=CREDIT_TYPES[credit])
    for name in (CREATOR, 'Test Person B'):
        creator = Creator.objects.create(
            gcd_official_name=name, sort_name=name)
        StoryCredit.objects.create(
            creator=CreatorNameDetail.objects.create(
                name=name, creator=creator,
                in_script=Script.objects.get(id=Script.LATIN_PK)),
            credit_type=credit_type, story=shared)

    matched = advanced_search(
        **{SEARCH_FIELD[credit]: '%s; Test Person B' % CREATOR})

    assert matched == {shared.id}


@pytest.mark.parametrize('credit', sorted(SEARCH_FIELD))
def test_empty_creator_segments_do_not_match_every_credit(
        credit, credited_stories):
    matched = advanced_search(**{SEARCH_FIELD[credit]: ';'})

    assert matched == set()


def test_unmatched_creator_returns_no_stories(credited_stories):
    assert advanced_search(script='Test Person Absent') == set()
