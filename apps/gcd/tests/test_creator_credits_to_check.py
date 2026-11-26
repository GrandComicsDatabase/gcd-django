# -*- coding: utf-8 -*-
"""Tests of the list of the credits to check of a creator."""

import re

import pytest
from django.urls import reverse

from apps.gcd.models import (CreditType, Issue, Publisher, Series, Story,
                             StoryCredit, StoryType)
from apps.gcd.models.creator import (Creator, CreatorNameDetail,
                                     NAME_TYPES, NameType)
from apps.gcd.models.story import CREDIT_TYPES
from apps.stddata.models import Country, Language, Script

LINK = re.compile(r"""href=['"]([^'"]+)['"]>Credits to Check<""")
NOTE = 'Non-official name selected without credited-flag'


@pytest.fixture
def world(db):
    """A creator with its official name and an issue for the stories."""
    latin = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK,
                  'name': 'Latin'})[0]
    country = Country.objects.get_or_create(
        id=912, defaults={'code': 'q2', 'name': 'Testland E'})[0]
    language = Language.objects.get_or_create(
        id=912, defaults={'code': 'q3', 'name': 'Testish E'})[0]
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1970)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series', year_began=1970,
        country=country, language=language, publisher=publisher,
        is_comics_publication=True, has_gallery=False,
        publication_dates='1970')
    issue = Issue.objects.create(number='1', series=series, sort_code=1,
                                 publication_date='1970')
    creator = Creator.objects.create(gcd_official_name='Some Writer',
                                     sort_name='Writer, Some')
    official = CreatorNameDetail.objects.create(
        name='Some Writer', creator=creator, is_official_name=True,
        in_script=latin)
    return {'creator': creator, 'official': official, 'issue': issue,
            'script': latin}


def _credit(world, name, type_name=None, script=None, **fields):
    """Return a credit under a new name of the creator, on a new story."""
    name_type = None
    if type_name:
        name_type = NameType.objects.get_or_create(
            id=NAME_TYPES[type_name], defaults={'type': type_name})[0]
    detail = CreatorNameDetail.objects.create(
        name=name, creator=world['creator'], type=name_type,
        in_script=script or world['script'])
    story = Story.objects.create(
        issue=world['issue'], sequence_number=Story.objects.count(),
        type=StoryType.objects.get_or_create(
            name='to-check-sequence', defaults={'sort_code': 99012})[0])
    return StoryCredit.objects.create(
        creator=detail, story=story, credit_type=CreditType.objects
        .get_or_create(id=CREDIT_TYPES['script'],
                       defaults={'name': 'script', 'sort_code': 1})[0],
        **fields)


def _listed(client, creator):
    """Follow the link of the creator page; return the listed stories."""
    page = client.get(reverse('show_creator', args=[creator.id]))
    links = LINK.findall(page.content.decode())
    assert len(links) == 1
    response = client.get(links[0])
    assert response.status_code == 200
    return set(response.context['table'].data.data)


def test_lists_the_credits_that_show_the_note(world, client):
    """Only the stories whose credit gets the note of the compare page."""
    credits = [
        _credit(world, 'S. Writer'),
        _credit(world, 'Writer S.', is_credited=True),
        _credit(world, 'Writer Studio', 'studio'),
        _credit(world, 'S. W. Smith', 'misspelled'),
        _credit(world, 'S. Writer Jr.', deleted=True),
    ] + [_credit(world, 'Writer %s' % kind, kind)
         for kind in ('house', 'ghost', 'joint')]
    other_script = Script.objects.get_or_create(
        code='Qabx', defaults={'number': 949, 'name': 'Test Script E'})[0]
    credits.append(_credit(world, 'Writer Name E', script=other_script))
    # not credited, but under the official name: the story stays out
    StoryCredit.objects.create(creator=world['official'],
                               story=credits[1].story,
                               credit_type=credits[1].credit_type)

    listed = _listed(client, world['creator'])

    expected = {credits[0].story, credits[3].story}
    assert listed == expected
    shown = {credit.story for credit in credits if not credit.deleted and
             NOTE in credit.creator.display_credit(credit, compare=True)}
    assert shown == expected


def test_link_only_for_a_creator_with_other_names(world, client):
    """The creator page links the list once the creator has other names."""
    page = client.get(reverse('show_creator', args=[world['creator'].id]))
    assert not LINK.findall(page.content.decode())

    _credit(world, 'S. Writer')

    assert _listed(client, world['creator'])
