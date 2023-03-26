# -*- coding: utf-8 -*-

import mock
import pytest

from apps.gcd.models import Story, Issue, Series
from apps.oi.models import StoryRevision, ReprintRevision, Changeset


@pytest.fixture
def patched_for_save():
    def story_uni(self):
        return self.title

    def issue_uni(self):
        return self.number

    # with mock.patch('apps.oi.models.LinkRevision.save') as save_mock, \
    with mock.patch('django.db.models.base.Model.save') as save_mock, \
            mock.patch('apps.gcd.models.story.Story.__str__', story_uni), \
            mock.patch('apps.gcd.models.issue.Issue.__str__', issue_uni):
        s = Series(name='Test Series')
        yield (save_mock,
               Story(title='origin',
                     issue=Issue(number='1', title='o issue', series=s)),
               Story(title='target',
                     issue=Issue(number='9', title='t issue', series=s)))


@pytest.fixture
def patched_for_commit(patched_for_save):
    # We don't actually need save patched, but it's harmless and easy.
    save_mock, origin, target = patched_for_save

    with mock.patch('apps.oi.models.StoryRevision.commit_to_display'), \
            mock.patch('apps.oi.models.StoryRevision.refresh_from_db'), \
            mock.patch('apps.oi.models.Revision.open',
                       new_callable=mock.PropertyMock) as open_mock:

        # By default, assume not open, and committed=True
        c = Changeset()
        open_mock.return_value = False
        origin_rev = StoryRevision(changeset=c, story=origin, committed=True)
        target_rev = StoryRevision(changeset=c, story=target, committed=True)

        # Need to track instance calls separately.
        origin_rev.commit_to_display = mock.MagicMock()
        target_rev.commit_to_display = mock.MagicMock()

        yield origin_rev, target_rev, open_mock


def test_save_stories_only(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = ReprintRevision(origin=origin, target=target)
    r.save()
    save_mock.assert_called_once_with()
    assert r.origin == origin
    assert r.target == target
    assert r.origin_issue == origin.issue
    assert r.target_issue == target.issue


def test_save_stories_and_issues_only(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = ReprintRevision(origin=origin,
                        origin_issue=origin.issue,
                        target=target,
                        target_issue=target.issue)
    r.save()
    save_mock.assert_called_once_with()

    # make sure nothing got changed.
    assert r.origin == origin
    assert r.target == target
    assert r.origin_issue == origin.issue
    assert r.target_issue == target.issue


def test_save_origin_mismatch(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = ReprintRevision(origin=origin,
                        origin_issue=target.issue,
                        target=target)
    with pytest.raises(ValueError) as exc_info:
        r.save()

    v = str(exc_info.value)
    assert "origin story and issue do not match" in v
    expected = "issue: '%s'; Issue: '%s'" % (origin.issue, target.issue)
    assert expected in v
    assert not save_mock.called


def test_save_target_mismatch(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = ReprintRevision(origin=origin,
                        target=target,
                        target_issue=origin.issue)
    with pytest.raises(ValueError) as exc_info:
        r.save()

    v = str(exc_info.value)
    assert "target story and issue do not match" in v
    expected = "issue: '%s'; Issue: '%s'" % (target.issue, origin.issue)
    assert expected in v
    assert not save_mock.called


def test_save_origin_rev_story_mismatch(patched_for_save):
    save_mock, origin, target = patched_for_save

    r = ReprintRevision(origin=origin, origin_issue=origin.issue,
                        origin_revision=StoryRevision(story=None,
                                                      issue=origin.issue),
                        target=target, target_issue=target.issue,
                        target_revision=StoryRevision(story=target,
                                                      issue=target.issue))
    with pytest.raises(ValueError) as exc_info:
        r.save()

    assert not save_mock.called
    v = str(exc_info.value)
    assert "origin story revision and origin story do not agree" in v
    assert ("'%s'; Story: '%s'" % (r.origin_revision.story, r.origin)) in v


def test_save_origin_rev_issue_mismatch(patched_for_save):
    save_mock, origin, target = patched_for_save

    r = ReprintRevision(origin=None, origin_issue=target.issue,
                        origin_revision=StoryRevision(story=origin,
                                                      issue=origin.issue),
                        target=target, target_issue=target.issue,
                        target_revision=StoryRevision(story=target,
                                                      issue=target.issue))
    with pytest.raises(ValueError) as exc_info:
        r.save()

    assert not save_mock.called
    v = str(exc_info.value)
    assert "origin story revision issue and origin issue do not agree" in v
    assert ("'%s'; Issue: '%s'" % (r.origin_revision.issue,
                                   r.origin_issue)) in v


def test_save_target_rev_story_mismatch(patched_for_save):
    save_mock, origin, target = patched_for_save

    r = ReprintRevision(origin=None, origin_issue=None,
                        origin_revision=StoryRevision(story=origin,
                                                      issue=origin.issue),
                        target=origin, target_issue=None,
                        target_revision=StoryRevision(story=target,
                                                      issue=target.issue))
    with pytest.raises(ValueError) as exc_info:
        r.save()

    assert not save_mock.called
    v = str(exc_info.value)
    assert "target story revision and target story do not agree" in v
    assert ("'%s'; Story: '%s'" % (r.target_revision.story, r.target)) in v


def test_save_target_rev_issue_mismatch(patched_for_save):
    save_mock, origin, target = patched_for_save

    r = ReprintRevision(origin=origin, origin_issue=origin.issue,
                        origin_revision=StoryRevision(story=origin,
                                                      issue=origin.issue),
                        target=None, target_issue=origin.issue,
                        target_revision=StoryRevision(story=target))
    with pytest.raises(ValueError) as exc_info:
        r.save()

    assert not save_mock.called
    v = str(exc_info.value)
    assert "target story revision issue and target issue do not agree" in v
    assert ("'%s'; Issue: '%s'" % (r.target_revision.issue,
                                   r.target_issue)) in v


def test_handle_prerequisites(patched_for_commit):
    origin_rev, target_rev, open_mock = patched_for_commit
    r = ReprintRevision(origin_revision=origin_rev,
                        target_revision=target_rev)

    r._handle_prerequisites({})

    assert not origin_rev.commit_to_display.called
    assert r.origin == r.origin_revision.story
    assert r.origin_issue == r.origin_revision.story.issue

    assert not target_rev.commit_to_display.called
    assert r.target == r.target_revision.story
    assert r.target_issue == r.target_revision.story.issue
