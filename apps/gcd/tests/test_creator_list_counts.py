# -*- coding: utf-8 -*-
"""Tests of the issue counts on the lists of creators of an object."""

import pytest

from apps.gcd.models import (CreditType, Feature, FeatureNameDetail,
                             FeatureType, Issue, Publisher, Series, Story,
                             StoryCredit, StoryType)
from apps.gcd.models.creator import Creator, CreatorNameDetail
from apps.stddata.models import Country, Date, Language, Script

SCRIPT = 1
EDITING = 6


def _name(text):
    """Create a creator with one name and return the name."""
    script = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    creator = Creator.objects.create(
        gcd_official_name=text, sort_name=text,
        birth_date=Date.objects.create(), death_date=Date.objects.create())
    return CreatorNameDetail.objects.create(name=text, creator=creator,
                                            in_script=script)


def _credit(name, story, credit_type, deleted=False):
    """Credit the name on the sequence with that type of credit."""
    StoryCredit.objects.create(
        creator=name, story=story, deleted=deleted,
        credit_type=CreditType.objects.get_or_create(
            id=credit_type,
            defaults={'name': 'type %d' % credit_type,
                      'sort_code': credit_type})[0])


def _catalog(feature_type_id):
    """Create a series of two issues whose sequences have one feature."""
    country = Country.objects.get_or_create(
        code='zc', defaults={'name': 'Testland C'})[0]
    language = Language.objects.get_or_create(
        code='zc', defaults={'name': 'Testish C'})[0]
    publisher = Publisher.objects.create(name='Publisher', country=country,
                                         year_began=1950)
    series = Series.objects.create(
        name='Series', sort_name='Series', year_began=1950, country=country,
        language=language, publisher=publisher, is_comics_publication=True,
        has_gallery=False, publication_dates='1950')
    feature = Feature.objects.create(
        name='Feature', sort_name='Feature', genre='', language=language,
        feature_type=FeatureType.objects.get_or_create(
            id=feature_type_id,
            defaults={'name': 'type %d' % feature_type_id})[0],
        year_first_published=1950, notes='')
    feature_name = FeatureNameDetail.objects.create(
        feature=feature, name='Feature', sort_name='Feature',
        is_official_name=True)
    stories = []
    for number in range(2):
        issue = Issue.objects.create(number=str(number + 1), series=series,
                                     sort_code=number, publication_date='1950',
                                     key_date='1950-01-00')
        story = Story.objects.create(
            issue=issue, sequence_number=0,
            type=StoryType.objects.get(name='comic story'))
        story.feature_name.add(feature_name)
        stories.append(story)
    ids = {'publisher': publisher.id, 'series': series.id,
           'feature': feature.id}
    return ids, stories


@pytest.mark.django_db
@pytest.mark.parametrize('kind, address, feature_type', [
    ('publisher', '/publisher/%d/%s/', 1),
    ('series', '/series/%d/details/%s/', 1),
    ('feature', '/feature/%d/%s/', 1),
    ('feature', '/feature/%d/%s/', 2)])
@pytest.mark.parametrize('names', ['creator_names', 'creators'])
def test_the_list_leaves_out_credits_for_editing(client, kind, address,
                                                 feature_type, names):
    """A count covers the issues it opens: credits for editing are not."""
    ids, stories = _catalog(feature_type)
    writer = _name('Writer and Editor')
    _credit(writer, stories[0], SCRIPT)
    _credit(writer, stories[1], EDITING)
    _credit(_name('Only Editor'), stories[0], EDITING)

    response = client.get(address % (ids[kind], names))

    assert response.status_code == 200
    counts = {row.id: row.issue_count
              for row in response.context['page'].object_list}
    listed = writer.id if names == 'creator_names' else writer.creator_id
    assert counts == {listed: 1}


@pytest.mark.django_db
def test_the_issues_of_a_name_on_a_feature_match_its_count(client):
    """Editing or a deleted credit on the feature does not list the issue."""
    ids, stories = _catalog(1)
    name = _name('Writer and Editor')
    no_feature = Story.objects.create(
        issue=stories[0].issue, sequence_number=1,
        type=StoryType.objects.get(name='comic story'))
    _credit(name, no_feature, SCRIPT)
    _credit(name, stories[0], EDITING)
    _credit(name, stories[0], SCRIPT, deleted=True)
    _credit(name, stories[1], SCRIPT)

    response = client.get('/feature/%d/creator_name/%d/issues/'
                          % (ids['feature'], name.id))

    assert response.status_code == 200
    assert response.context['page'].paginator.count == 1
