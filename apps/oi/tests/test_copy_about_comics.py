import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Series, Story, StoryType, STORY_TYPES
from apps.oi import states
from apps.oi.models import (BiblioEntryRevision, Changeset, CTYPES,
                            IssueRevision, ReprintRevision, StoryRevision)

ABOUT_COMICS = STORY_TYPES['about comics']


@pytest.fixture
def about_comics_story(any_indexer, any_added_series):
    """An "about comics" sequence in a series which has them."""
    Series.objects.filter(id=any_added_series.id).update(
      has_about_comics=True)
    changeset = Changeset.objects.create(
      state=states.OPEN, indexer=any_indexer, change_type=CTYPES['issue_add'])
    issue_revision = IssueRevision.objects.create(
      changeset=changeset, series=any_added_series, number='1',
      no_title=True, no_volume=True, no_isbn=True, no_barcode=True,
      no_rating=True, no_indicia_frequency=True, no_editing=True,
      publication_date='May 1990', key_date='1990-05-00')
    issue_revision.commit_to_display()
    revision = StoryRevision.objects.create(
      changeset=changeset, issue=issue_revision.issue,
      type=StoryType.objects.get(id=ABOUT_COMICS), sequence_number=0,
      title='How Comics Are Made', no_editing=True, page_count=4)
    # as done by the add_story view for "about comics" sequences
    biblio_revision = BiblioEntryRevision(storyrevision_ptr=revision)
    biblio_revision.__dict__.update(revision.__dict__)
    biblio_revision.save()
    StoryRevision.objects.get(id=revision.id).commit_to_display()
    return Story.objects.get(issue=issue_revision.issue)


@pytest.fixture
def target_revision(client, any_indexer, any_added_issue):
    """The reserved issue revision of an issue to copy into."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    client.post(reverse('reserve_revision',
                        kwargs={'model_name': 'issue',
                                'id': any_added_issue.id}))
    return IssueRevision.objects.get(issue=any_added_issue,
                                     changeset__state=states.OPEN)


def _copied(issue_revision):
    return issue_revision.changeset.storyrevisions.filter(
      issue=issue_revision.issue, type_id=ABOUT_COMICS).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('has_about_comics', [False, True])
def test_copy_of_about_comics_sequence(client, about_comics_story,
                                       target_revision, has_about_comics):
    Series.objects.filter(id=target_revision.series_id).update(
      has_about_comics=has_about_comics)

    client.post(reverse('confirm_copy_story',
                        kwargs={'issue_revision_id': target_revision.id,
                                'story_id': about_comics_story.id,
                                'sequence_number': 0}))

    assert _copied(target_revision) is has_about_comics


@pytest.mark.django_db
def test_matching_sequence_refuses_about_comics(client, about_comics_story,
                                               target_revision):
    assert not target_revision.series.has_about_comics
    reprint_revision = ReprintRevision.objects.create(
      changeset=target_revision.changeset, origin=about_comics_story,
      target_issue=target_revision.issue)

    client.post(reverse('create_matching_sequence',
                        kwargs={'reprint_revision_id': reprint_revision.id,
                                'issue_id': target_revision.issue.id,
                                'story_id': about_comics_story.id}))

    assert not _copied(target_revision)
