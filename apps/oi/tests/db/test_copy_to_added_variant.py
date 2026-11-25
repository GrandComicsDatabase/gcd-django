# -*- coding: utf-8 -*-
"""Copying a cover sequence into a variant which is not approved yet."""

import mock
import pytest
from django.contrib.auth.models import Permission
from django.forms import CheckboxInput
from django.template.loader import render_to_string
from django.urls import reverse

from apps.gcd.models import (
    Character, CharacterNameDetail, CharacterRelation, CharacterRelationType,
    CREDIT_TYPES, Creator, CreatorNameDetail, CreditType, Feature,
    FeatureNameDetail, FeatureRelation, FeatureRelationType, FeatureType,
    Issue, STORY_TYPES, Series, StoryCharacter, StoryCredit, StoryType)
from apps.oi import states
from apps.oi.models import (
    CTYPES, IssueRevision, RevisionLock, StoryCharacterRevision, StoryRevision)
from apps.stddata.models import Date, Language, Script

UPDATE_ALL = 'apps.stats.models.CountStats.objects.update_all_counts'
BUTTON = 'Copy Cover Sequence'


@pytest.fixture
def cover(any_added_story):
    """Return an approved cover sequence of the base issue of the variant."""
    any_added_story.type = StoryType.objects.get(name='cover')
    any_added_story.save()
    return any_added_story


@pytest.fixture
def cover_reprint(any_added_story):
    """Return an approved cover reprinted on an interior page."""
    any_added_story.type = StoryType.objects.get(
      name='cover reprint (on interior page)')
    any_added_story.save()
    return any_added_story


@pytest.fixture(params=['issue_add', 'variant_add'])
def new_variant_rev(request, any_variant_adding_changeset, any_added_issue,
                    variant_add_values):
    """Return a new variant as each of the two ways of adding one does."""
    changeset = any_variant_adding_changeset
    changeset.change_type = CTYPES[request.param]
    changeset.save()
    if request.param == 'variant_add':
        # The revision of the base issue is always the older one.
        RevisionLock.objects.create(locked_object=any_added_issue,
                                    changeset=changeset)
        IssueRevision.clone(data_object=any_added_issue, changeset=changeset)
    brand = variant_add_values.pop('brand_emblem')
    revision = IssueRevision(changeset=changeset, **variant_add_values)
    revision.save()
    revision.brand_emblem.set([brand])
    return IssueRevision.objects.get(pk=revision.pk)


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client of the indexer holding the changeset."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


@pytest.fixture
def other_language():
    """Return a language differing from the one of the base issue."""
    return Language.objects.create(code='YZZ', name='Other Language')


@pytest.fixture
def foreign_variant_rev(any_added_variant_rev, other_language):
    """Return the new variant, in a series with another language."""
    series = Series.objects.get(pk=any_added_variant_rev.series_id)
    series.pk = None
    series.language = other_language
    series.save()
    any_added_variant_rev.series = series
    any_added_variant_rev.save()
    return any_added_variant_rev


def add_credit(story):
    """Give the story a credit and return the name of its creator."""
    creator = Creator.objects.create(
      gcd_official_name='Test Creator', birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='',
      birth_date=Date.objects.create(year='1950'))
    script = Script.objects.create(code='Tst', number=999,
                                   name='Test Script')
    name = CreatorNameDetail.objects.create(
      name='Test Creator', creator=creator, is_official_name=True,
      in_script=script)
    credit_type, _ = CreditType.objects.get_or_create(
      id=CREDIT_TYPES['script'],
      defaults={'name': 'script', 'sort_code': CREDIT_TYPES['script']})
    StoryCredit.objects.create(
      story=story, creator=name, credit_type=credit_type, signed_as='',
      credited_as='', sourced_by='', credit_name='')
    return name


def add_character(language, name='Test Character'):
    """Create a character and return its official name."""
    character = Character.objects.create(
      name=name, disambiguation='', language=language, description='',
      notes='')
    return CharacterNameDetail.objects.create(
      name=name, character=character, is_official_name=True)


def add_feature(language, name):
    """Create a feature and return its official name."""
    feature_type, _ = FeatureType.objects.get_or_create(
      id=1, defaults={'name': 'feature'})
    feature = Feature.objects.create(
      name=name, sort_name=name, genre='', language=language,
      feature_type=feature_type, notes='')
    return FeatureNameDetail.objects.create(
      feature=feature, name=name, sort_name=name, is_official_name=True)


def translate_feature(source, translation):
    """Record that one feature name is translated into the other one."""
    relation_type, _ = FeatureRelationType.objects.get_or_create(
      id=1, defaults={'name': 'translation', 'description': '',
                      'reverse_description': ''})
    FeatureRelation.objects.create(
      from_feature=source.feature, to_feature=translation.feature,
      relation_type=relation_type, notes='')


def copied(story, issue_revision):
    """Copy the story with its credits and characters."""
    return StoryRevision.copied_revision(
      story, issue_revision.changeset, issue_revision=issue_revision,
      copy_credit_info=True, copy_characters=True)


def changeset_html(changeset):
    """Render the part of the edit page which holds the copy button."""
    return render_to_string('oi/edit/issue_changeset.html',
                            {'changeset': changeset, 'CTYPES': CTYPES})


def press_copy_cover(client, issue_revision, story):
    """Press Copy Cover Sequence and return where the story is confirmed."""
    response = client.get(
      reverse('add_story', kwargs={
        'issue_revision_id': issue_revision.id,
        'changeset_id': issue_revision.changeset_id}),
      {'copy_cover': BUTTON, 'added_sequence_number': '0'})
    assert response.status_code == 302
    assert 'select_multiple_sequences' in response.url
    return reverse('confirm_copy_story', kwargs={
      'issue_revision_id': issue_revision.id, 'story_id': story.id,
      'sequence_number': 0})


def copy_through_views(client, issue_revision, cover, **options):
    """Press Copy Cover Sequence, confirm, and return the last response."""
    url = press_copy_cover(client, issue_revision, cover)
    response = client.post(url, options)
    assert response.status_code == 200
    return client.post(
      url, dict(options, cover_plan=response.context['cover_plan']))


def unchanged_form_data(response):
    """Return what a browser posts to save the edit page as it is."""
    forms = [response.context['form']]
    for name in ('credits_formset', 'characters_formset', 'groups_formset'):
        formset = response.context[name]
        forms += [formset.management_form, *formset.forms]
    data = {'save': 'Save'}
    for form in forms:
        for field in form:
            value = field.value()
            if isinstance(field.field.widget, CheckboxInput):
                if value:
                    data[field.html_name] = 'on'
            elif isinstance(value, (list, tuple)):
                data[field.html_name] = [str(item) for item in value]
            elif value is not None:
                data[field.html_name] = str(value)
    return data


@pytest.mark.django_db
def test_copy_keeps_the_issue_empty(any_added_variant_rev, cover,
                                    any_language):
    """The copy waits for the variant, as number 0 with all its data."""
    creator = add_credit(cover)
    character = add_character(any_language)
    StoryCharacter.objects.create(story=cover, character=character, notes='')

    revision = copied(cover, any_added_variant_rev)

    revision.refresh_from_db()
    assert revision.issue is None
    assert revision.sequence_number == 0
    assert revision.type_id == STORY_TYPES['cover']
    assert [credit.creator for credit
            in revision.story_credit_revisions.all()] == [creator]
    assert [appearing.character for appearing
            in revision.story_character_revisions.all()] == [character]
    assert list(any_added_variant_rev.active_stories()) == [revision]


@pytest.mark.django_db
def test_copy_translates_to_the_language_of_the_variant(
        foreign_variant_rev, cover, any_language, other_language):
    """Characters and features follow the series of the variant revision."""
    third_language = Language.objects.create(code='WZZ', name='Third')
    character = add_character(any_language)
    StoryCharacter.objects.create(story=cover, character=character, notes='')
    translated_character = add_character(other_language, name='Translated')
    relation_type, _ = CharacterRelationType.objects.get_or_create(
      id=1, defaults={'type': 'translation', 'reverse_type': 'translation'})
    CharacterRelation.objects.create(
      from_character=character.character,
      to_character=translated_character.character,
      relation_type=relation_type, notes='')
    translated = add_feature(any_language, 'Translated')
    translation = add_feature(other_language, 'Translation')
    translate_feature(translated, translation)
    copy = add_feature(any_language, 'Translation Of Original')
    original = add_feature(other_language, 'Original')
    translate_feature(original, copy)
    sibling = add_feature(any_language, 'Sibling')
    common_source = add_feature(third_language, 'Common Source')
    other_sibling = add_feature(other_language, 'Other Sibling')
    translate_feature(common_source, sibling)
    translate_feature(common_source, other_sibling)
    cover.feature_name.add(translated, copy, sibling)

    revision = copied(cover, foreign_variant_rev)

    revision.refresh_from_db()
    assert revision.issue is None
    assert revision.sequence_number == 0
    assert revision.type_id == STORY_TYPES['cover']
    assert revision.title == ''
    assert [appearing.character for appearing
            in revision.story_character_revisions.all()] == [
                translated_character]
    assert set(revision.feature_name.all()) == {translation, original,
                                                other_sibling}


@pytest.mark.django_db
def test_approval_puts_the_copy_on_the_new_variant(new_variant_rev, cover,
                                                   any_indexer):
    """Approval creates the variant and moves the copied cover onto it."""
    changeset = new_variant_rev.changeset
    revision = copied(cover, new_variant_rev)
    changeset.state = states.REVIEWING
    changeset.approver = any_indexer
    changeset.save()

    with mock.patch(UPDATE_ALL):
        changeset.approve()

    revision.refresh_from_db()
    variant = IssueRevision.objects.get(pk=new_variant_rev.pk).issue
    assert variant.variant_of == cover.issue
    assert revision.issue == variant
    assert revision.story.issue == variant
    assert revision.story.sequence_number == 0
    assert revision.story.type_id == STORY_TYPES['cover']
    assert list(variant.active_stories()) == [revision.story]
    assert Issue.objects.get(pk=cover.issue.pk).active_stories().get() == cover


@pytest.mark.django_db
def test_copy_cover_through_the_views(indexer_client, new_variant_rev, cover,
                                      any_language):
    """The copy can be confirmed, edited, saved and compared without issue."""
    creator = add_credit(cover)
    character = add_character(any_language)
    StoryCharacter.objects.create(story=cover, character=character, notes='')
    changeset = new_variant_rev.changeset

    response = copy_through_views(indexer_client, new_variant_rev, cover,
                                  copy_credit_info='on', copy_characters='on')
    assert response.status_code == 302

    revision = changeset.storyrevisions.get()
    assert response.url == reverse('edit_revision', kwargs={
      'model_name': 'story', 'id': revision.id})
    assert revision.issue is None
    assert revision.sequence_number == 0
    assert revision.type_id == STORY_TYPES['cover']

    page = indexer_client.get(response.url)
    assert page.status_code == 200
    response = indexer_client.post(
      reverse('process_revision', kwargs={'model_name': 'story',
                                          'id': revision.id}),
      unchanged_form_data(page))
    assert response.status_code == 302, page.context['form'].errors

    revision.refresh_from_db()
    assert revision.issue is None
    assert revision.type_id == STORY_TYPES['cover']
    assert [credit.creator for credit
            in revision.story_credit_revisions.filter(deleted=False)] == [
                creator]
    assert [appearing.character for appearing
            in revision.story_character_revisions.filter(deleted=False)] == [
                character]
    assert indexer_client.get(reverse(
      'compare', kwargs={'id': changeset.id})).status_code == 200


@pytest.mark.django_db
def test_copy_cover_reprint_through_the_views(indexer_client,
                                              new_variant_rev,
                                              cover_reprint):
    """A cover reprint is copied at once; its form saves it only as a cover."""
    changeset = new_variant_rev.changeset
    url = press_copy_cover(indexer_client, new_variant_rev, cover_reprint)

    response = indexer_client.post(url)

    assert response.status_code == 302
    revision = changeset.storyrevisions.get()
    assert response.url == reverse('edit_revision', kwargs={
      'model_name': 'story', 'id': revision.id})
    assert revision.issue is None
    assert revision.sequence_number == 0
    assert revision.type_id == STORY_TYPES['cover reprint (on interior page)']
    page = indexer_client.get(response.url)
    assert page.status_code == 200

    url = reverse('process_revision', kwargs={'model_name': 'story',
                                              'id': revision.id})
    data = unchanged_form_data(page)
    response = indexer_client.post(url, data)
    assert response.status_code == 200
    assert 'type' in response.context['form'].errors
    revision.refresh_from_db()
    assert revision.type_id == STORY_TYPES['cover reprint (on interior page)']

    data['type'] = str(STORY_TYPES['cover'])
    response = indexer_client.post(url, data)
    assert response.status_code == 302
    revision.refresh_from_db()
    assert revision.issue is None
    assert revision.type_id == STORY_TYPES['cover']


@pytest.mark.django_db
def test_compare_and_copy_keeps_the_characters_of_a_copied_cover(
        indexer_client, new_variant_rev, cover, any_added_story_rev,
        any_language):
    """Copying characters from a cover in the same language removes none."""
    names = [add_character(any_language, name=name)
             for name in ('Hero', 'Sidekick')]
    for name in names:
        StoryCharacter.objects.create(story=cover, character=name, notes='')
        StoryCharacterRevision.objects.create(
          changeset=any_added_story_rev.changeset,
          story_revision=any_added_story_rev, character=name, notes='')
    revision = copied(cover, new_variant_rev)

    response = indexer_client.post(
      reverse('compare_stories_copy', kwargs={'story_revision_id': revision.id,
                                              'story_id': cover.id}),
      {'field_to_copy': ['characters'], 'copy_select': 'Copy'})

    assert response.status_code == 302
    active = revision.story_character_revisions.filter(deleted=False)
    assert {appearing.character for appearing in active} == set(names)


@pytest.mark.django_db
def test_approved_variant_can_still_copy_its_cover(
        indexer_client, cover, any_added_variant, any_editing_changeset):
    """A variant whose issue exists takes a cover through the same views."""
    variant_rev = IssueRevision.clone(data_object=any_added_variant,
                                      changeset=any_editing_changeset)

    response = copy_through_views(indexer_client, variant_rev, cover)

    assert response.status_code == 302
    revision = any_editing_changeset.storyrevisions.get()
    assert revision.issue == any_added_variant
    assert revision.sequence_number == 0
    assert revision.type_id == STORY_TYPES['cover']


@pytest.mark.django_db
def test_button_shown_on_new_variant_with_artwork_difference(
        any_added_variant_rev):
    """A new variant with different artwork offers the copy."""
    assert BUTTON in changeset_html(any_added_variant_rev.changeset)


@pytest.mark.parametrize('status', [1, 2])
@pytest.mark.django_db
def test_button_absent_without_artwork_difference(any_added_variant_rev,
                                                  status):
    """A variant with the artwork of its base does not offer the copy."""
    any_added_variant_rev.variant_cover_status = status
    any_added_variant_rev.save()
    assert BUTTON not in changeset_html(any_added_variant_rev.changeset)


@pytest.mark.django_db
def test_button_absent_when_variant_holds_a_sequence(any_added_variant_rev):
    """A variant holding its one sequence does not offer the copy."""
    StoryRevision.objects.create(
      changeset=any_added_variant_rev.changeset, sequence_number=0,
      type=StoryType.objects.get(name='cover'))
    assert BUTTON not in changeset_html(any_added_variant_rev.changeset)
