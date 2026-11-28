"""Fixtures for the tests of bulk changes."""
import pytest

from django.contrib.auth.models import Permission, User

from apps.gcd.models import SeriesPublicationType, StoryType
from apps.indexer.models import Indexer
from apps.mycomics.models import Collector, ConditionGradeScale
from apps.oi import states
from apps.oi.models import (
    Changeset, IssueRevision, SeriesRevision, StoryRevision, CTYPES,
    _get_revision_lock)


@pytest.fixture
def bulk_change(any_indexer):
    """
    Return a function that builds a bulk change by hand: for each object a
    lock and a cloned revision with the given values, in a new OPEN bulk
    change of any_indexer or in the given changeset.
    """
    def build(objects, rev_class, changeset=None, **values):
        if changeset is None:
            changeset = Changeset.objects.create(
              indexer=any_indexer, state=states.OPEN,
              change_type=CTYPES['bulk'])
        for data_object in objects:
            assert _get_revision_lock(data_object, changeset) is not None
            revision = rev_class.clone(data_object=data_object,
                                       changeset=changeset)
            for name, value in values.items():
                setattr(revision, name, value)
            revision.save()
        return changeset
    return build


@pytest.fixture
def sequence_change(bulk_change):
    """
    Return a function that builds a bulk change of sequences, with the
    unchanged revisions of their issues that anchor them.
    """
    def build(stories, **values):
        changeset = bulk_change(stories, StoryRevision, **values)
        return bulk_change([story.issue for story in stories],
                           IssueRevision, changeset=changeset)
    return build


@pytest.fixture
def approve_change(any_approver):
    """
    Return a function that submits a change and approves it.  The points
    of the indexer and of the approver are read again, as a new request
    would.
    """
    def approve(changeset):
        changeset.submit()
        changeset.assign(any_approver)
        changeset.approve()
        changeset.indexer.indexer.refresh_from_db()
        any_approver.indexer.refresh_from_db()
    return approve


@pytest.fixture
def indicia_publisher_add_values(indicia_publisher_add_values):
    """
    The values of the shared fixture with years that cover 1947, the key
    date of the approved issues, so that their edit form offers it.
    """
    return dict(indicia_publisher_add_values, year_began=1940)


@pytest.fixture
def approved_issues(any_added_issue, any_adding_changeset):
    """Three approved issues of one series."""
    issues = [any_added_issue]
    for number in ('43', '44'):
        revision = IssueRevision(
          changeset=any_adding_changeset, number=number, after=issues[-1],
          series=any_added_issue.series, no_title=True, no_volume=True,
          indicia_publisher=any_added_issue.indicia_publisher,
          publication_date='January 1947', key_date='1947-01-00',
          price='0.10 USD', indicia_frequency='monthly')
        revision.save()
        revision.commit_to_display()
        issues.append(revision.issue)
    return issues


@pytest.fixture
def approved_series(any_added_publisher, any_adding_changeset, any_country,
                    any_language):
    """
    Three approved series of one publisher, in id order, with the same
    format fields; the name of the second has a leading article.
    """
    series = []
    for name in ('Series One', 'The Series Two', 'Series Three'):
        revision = SeriesRevision(
          changeset=any_adding_changeset, name=name,
          leading_article=name.startswith('The '), year_began=1990,
          publication_type=SeriesPublicationType.objects.get_or_create(
            name='magazine')[0],
          is_comics_publication=True, country=any_country,
          language=any_language, publisher=any_added_publisher,
          color='four colors', dimensions='standard Modern Age US',
          paper_stock='glossy', binding='Saddle-stitched',
          publishing_format='ongoing series')
        revision.save()
        revision.commit_to_display()
        series.append(revision.series)
    return series


@pytest.fixture
def approved_variant(approved_issues, any_adding_changeset):
    """An approved variant of the last of the approved issues."""
    base = approved_issues[-1]
    revision = IssueRevision(
      changeset=any_adding_changeset, number=base.number, after=base,
      series=base.series, variant_of=base, variant_name='Direct',
      no_title=True, no_volume=True,
      indicia_publisher=base.indicia_publisher,
      publication_date='January 1947', key_date='1947-01-00',
      price='0.10 USD', indicia_frequency='monthly')
    revision.save()
    revision.commit_to_display()
    return revision.issue


@pytest.fixture
def approved_stories(approved_issues, any_adding_changeset):
    """
    One approved sequence in each of the first two issues, with sequence
    numbers 1 and 2.
    """
    stories = []
    for number, issue in enumerate(approved_issues[:2], start=1):
        revision = StoryRevision(
          changeset=any_adding_changeset, issue=issue, sequence_number=number,
          title='Story %d' % number,
          type=StoryType.objects.get(name='comic story'),
          script='Test Person One', pencils='Test Person Two',
          inks='Test Person Three', letters='Test Person Four',
          no_colors=True, no_editing=True, page_count=8,
          genre='superhero')
        revision.save()
        revision.commit_to_display()
        stories.append(revision.story)
    return stories


@pytest.fixture
def any_approver(any_country):
    """An indexer who may reserve and approve changes."""
    user = User.objects.create_user('approver', email='noreply@comics.org',
                                    password='approver')
    Indexer.objects.create(user=user, country=any_country)
    user.user_permissions.add(*Permission.objects.filter(
      content_type__app_label='indexer',
      codename__in=['can_reserve', 'can_approve']))
    return user


@pytest.fixture
def indexer(any_indexer, any_language):
    """An indexer with the collector that a confirmed account gets."""
    Collector.objects.create_collector(
      any_indexer,
      grade_system=ConditionGradeScale.objects.create(name='Test scale'),
      default_language=any_language)
    return any_indexer


@pytest.fixture
def reserving_indexer(indexer):
    """An indexer who may reserve changes."""
    indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    return indexer
