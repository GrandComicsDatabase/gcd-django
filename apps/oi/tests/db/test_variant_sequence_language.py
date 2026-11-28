# -*- coding: utf-8 -*-
"""The language of the sequence form of a variant that is being added."""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Series, StoryType
from apps.oi import states
from apps.oi.models import (
    CTYPES, Changeset, IssueRevision, RevisionLock, StoryRevision)
from apps.stddata.models import Language


@pytest.fixture
def indexer_client(client, any_indexer):
    """Return a client of the indexer holding the changeset."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return client


@pytest.fixture
def variant_of_moved_issue(any_indexer, any_added_issue):
    """
    Return a variant added in the change which first moved its base issue
    to a series in another language.
    """
    changeset = Changeset(state=states.OPEN, indexer=any_indexer,
                          change_type=CTYPES['issue'])
    changeset.save()
    RevisionLock.objects.create(locked_object=any_added_issue,
                                changeset=changeset)
    base = IssueRevision.clone(data_object=any_added_issue,
                               changeset=changeset)
    series = Series.objects.get(pk=any_added_issue.series_id)
    series.pk = None
    series.language = Language.objects.get_or_create(
      code='de', defaults={'name': 'German'})[0]
    series.save()
    base.series = series
    base.save()
    # what Add Variant Issue does
    variant = IssueRevision(variant_name='varied variant',
                            indicia_publisher=base.indicia_publisher)
    variant.save_added_revision(changeset=changeset, series=base.series,
                                variant_of=base.issue)
    changeset.change_type = CTYPES['variant_add']
    changeset.save()
    return variant


def offered_language(response):
    """Return the language code and the adventure genre of the form."""
    form = response.context['form']
    return (form.fields['language_code'].initial,
            dict(form.fields['genre'].choices)['adventure'])


@pytest.mark.django_db
def test_edit_form_has_the_language_of_the_add_form(
      indexer_client, variant_of_moved_issue, story_add_values):
    variant = variant_of_moved_issue
    response = indexer_client.get(
      reverse('add_story', kwargs={'issue_revision_id': variant.id,
                                   'changeset_id': variant.changeset_id}),
      {'added_sequence_number': '0'})
    assert response.status_code == 200
    assert offered_language(response) == ('de', 'adventure / Abenteuer')

    cover = StoryRevision(changeset=variant.changeset,
                          **dict(story_add_values, issue=None,
                                 sequence_number=0,
                                 type=StoryType.objects.get(name='cover')))
    cover.save()
    response = indexer_client.get(
      reverse('edit_revision', kwargs={'model_name': 'story',
                                       'id': cover.id}))

    assert response.status_code == 200
    assert offered_language(response) == ('de', 'adventure / Abenteuer')
