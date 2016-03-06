# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from django.utils.html import conditional_escape as esc

from apps.gcd.models import Story, Issue, Series, Reprint


@pytest.yield_fixture
def patched_for_save():
    with mock.patch('apps.gcd.models.reprint.GcdLink.save') as save_mock:
        yield (save_mock,
               Story(title='origin', issue=Issue(number='1', title='o issue')),
               Story(title='target', issue=Issue(number='9', title='t issue')))


def test_save_fields_none_both_stories(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = Reprint(origin=origin, target=target)
    r.save()
    save_mock.assert_called_once_with()
    assert r.origin == origin
    assert r.target == target
    assert r.origin_issue == origin.issue
    assert r.target_issue == target.issue


def test_save_fields_none_both_issues(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = Reprint(origin_issue=origin.issue, target_issue=target.issue)
    r.save()
    save_mock.assert_called_once_with()
    assert r.origin is None
    assert r.target is None
    assert r.origin_issue == origin.issue
    assert r.target_issue == target.issue


def test_save_fields_origin_with_story(patched_for_save):
    save_mock, origin, target = patched_for_save
    # Put in nonsense target_issue to show that save() properly ignores it
    # as target is not in the update_fields list.  It would be weird but
    # possible for a caller to do this.
    nonsense = Issue(number='[nn]')
    r = Reprint(origin=origin, target=target, target_issue=nonsense)
    r.save(update_fields=['origin'])
    save_mock.assert_called_once_with(update_fields=['origin', 'origin_issue'])
    assert r.origin == origin
    assert r.target == target
    assert r.origin_issue == origin.issue
    assert r.target_issue == nonsense


def test_save_fields_target_with_story(patched_for_save):
    save_mock, origin, target = patched_for_save
    r = Reprint(origin_issue=origin.issue, target=target)
    r.save(update_fields=['target'])
    save_mock.assert_called_once_with(update_fields=['target', 'target_issue'])
    assert r.origin is None
    assert r.target == target
    assert r.origin_issue == origin.issue
    assert r.target_issue == target.issue


@pytest.yield_fixture
def patched_for_strings():
    def full_name(self):
        return self.number

    def get_url(self):
        return 'http://www.comics.org/issue/%d/' % self.id

    def story_name(self):
        return self.title

    with mock.patch('apps.gcd.models.issue.Issue.get_absolute_url', get_url), \
            mock.patch('apps.gcd.models.issue.Issue.full_name', full_name), \
            mock.patch('apps.gcd.models.story.Story.__unicode__', story_name):
        yield


def _build_reprint(origin_story, target_story, origin_base, notes):
    s = Series(name='Test Series')
    origin_issue = Issue(id=1, number='1', series=s)
    target_issue = Issue(id=2, number='2', series=s)
    origin = Story(id=1, title='origin', issue=origin_issue)
    target = Story(id=2, title='target', issue=target_issue)
    assert '%s' % origin == 'origin'

    r = Reprint(origin_issue=origin_issue,
                target_issue=target_issue,
                origin=(origin if origin_story else None),
                target=(target if target_story else None),
                notes=notes)
    base_issue = origin_issue if origin_base else target_issue

    # Pull stories from the reprint because they may be None.
    far_story = r.target if origin_base else r.origin
    far_issue = target_issue if origin_base else origin_issue

    return r, base_issue, far_issue, far_story


@pytest.mark.parametrize('origin_story', (True, False))
@pytest.mark.parametrize('target_story', (True, False))
@pytest.mark.parametrize('origin_base', (True, False))
@pytest.mark.parametrize('notes', ('', 'a note'))
def test_compare_string_target_story(origin_story, target_story,
                                     origin_base, notes, patched_for_strings):
    r, base_issue, far_issue, far_story = _build_reprint(origin_story,
                                                         target_story,
                                                         origin_base, notes)
    actual = r.get_compare_string(base_issue)

    expected = 'in ' if origin_base else 'from '
    if far_story:
        expected += esc(far_issue.full_name()) + ' <i>sequence</i> '
    expected += ('<a target="_blank" href="%s' % far_issue.get_absolute_url())
    if far_story:
        expected += '#%d' % far_story.id
    expected += '">%s</a>' % (
        esc(far_story if far_story else far_issue.full_name()))
    if notes:
        expected += ' [%s]' % notes

    assert actual == expected


@pytest.mark.parametrize('origin_story', (True, False))
@pytest.mark.parametrize('target_story', (True, False))
def test_unicode(origin_story, target_story, patched_for_strings):
    # NOTE: origin_base and notes are irrelevant here, any value is fine.
    r, base_issue, far_issue, far_story = _build_reprint(origin_story,
                                                         target_story,
                                                         origin_base=False,
                                                         notes='')
    actual = unicode(r)

    prefix = (('%s of ' % r.origin if origin_story else '') +
              unicode(r.origin_issue))
    suffix = (('%s of ' % r.target if target_story else '') +
              unicode(r.target_issue))
    expected = '%s is reprinted in %s' % (prefix, suffix)
    if not origin_story:
        expected = 'material from %s' % expected

    assert actual == expected
