# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from django.db.models import QuerySet

from apps.gcd.models import Series, Issue, Story
from apps.gcd.models.story import STORY_TYPES

# TODO: We really shouldn't be depending on the OI here.
from apps.oi import states


ISSUE_PATH = 'apps.gcd.models.issue.Issue'
ANY_SERIES = Series(name='Test Series', year_began=1940)


def test_has_keywords():
    with mock.patch('%s.keywords' % ISSUE_PATH) as kw_mock:
        i = Issue()

        kw_mock.exists.return_value = False
        assert i.has_keywords() is False

        kw_mock.exists.return_value = True
        assert i.has_keywords() is True


def test_other_variants():
    with mock.patch('%s.variant_of' % ISSUE_PATH,
                    spec=Issue) as vo_mock, \
            mock.patch('%s.variant_set' % ISSUE_PATH,
                       spec=QuerySet) as vs_mock:

        v1, v2, v3, v4 = [mock.MagicMock(spec=Issue) for x in range(0, 4)]

        vo_mock.variant_set.exclude.return_value \
                           .exclude.return_value = [v1, v2]
        vs_mock.all.return_value.exclude.return_value = [v3, v4]

        i = Issue()
        assert i.other_variants() == [v1, v2]
        first_exclude = i.variant_of.variant_set.exclude
        first_exclude.assert_called_once_with(id=i.id)
        first_exclude.return_value.exclude.assert_called_once_with(
            deleted=True)

        i.variant_of = None
        assert i.other_variants() == [v3, v4]
        i.variant_set.all.assert_called_once_with()
        i.variant_set.all.return_value.exclude.assert_called_once_with(
            deleted=True)


def test_can_upload_variants():
    with mock.patch('%s.revisions' % ISSUE_PATH) as rev_mock, \
            mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = True
        rev_mock.filter.return_value.count.return_value = 0
        i = Issue(number='1', series=ANY_SERIES)

        can_upload_variants = i.can_upload_variants()
        assert bool(can_upload_variants) is True
        rev_mock.filter.assert_called_once_with(
            changeset__state__in=states.ACTIVE, deleted=True)


def test_cant_upload_variants_no_covers():
    with mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = False
        i = Issue(number='1', series=ANY_SERIES)

        can_upload_variants = i.can_upload_variants()
        assert bool(can_upload_variants) is False


def test_cant_upload_variants_active_revisions():
    with mock.patch('%s.revisions' % ISSUE_PATH) as rev_mock, \
            mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = True
        rev_mock.filter.return_value.count.return_value = 1
        i = Issue(number='1', series=ANY_SERIES)

        can_upload_variants = i.can_upload_variants()
        assert bool(can_upload_variants) is False
        rev_mock.filter.assert_called_once_with(
            changeset__state__in=states.ACTIVE, deleted=True)


@pytest.yield_fixture
def re_issue_mocks():
    """ Dictionary of mocks for use with testing for reprints. """
    with mock.patch('%s.from_reprints' % ISSUE_PATH) as fr_mock, \
            mock.patch('%s.to_reprints' % ISSUE_PATH) as tr_mock, \
            mock.patch('%s.from_issue_reprints' % ISSUE_PATH) as fir_mock, \
            mock.patch('%s.to_issue_reprints' % ISSUE_PATH) as tir_mock:

        mocks = {
            'fr': fr_mock,
            'tr': tr_mock,
            'fir': fir_mock,
            'tir': tir_mock,
        }
        mocks['fr'].count.return_value = 0
        mocks['tr'].exclude.return_value.count.return_value = 0
        mocks['fir'].count.return_value = 0
        mocks['tir'].count.return_value = 0

        yield mocks


def test_no_reprints(re_issue_mocks):
    i = Issue(number='1', series=ANY_SERIES)
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is False
    re_issue_mocks['tr'].exclude.assert_called_once_with(
        target__type__id=STORY_TYPES['promo'])


def test_has_from_reprints(re_issue_mocks):
    i = Issue(number='1', series=ANY_SERIES)
    re_issue_mocks['fr'].count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True


def test_has_to_reprints(re_issue_mocks):
    i = Issue(number='1', series=ANY_SERIES)
    re_issue_mocks['tr'].exclude.return_value.count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True
    re_issue_mocks['tr'].exclude.assert_called_once_with(
        target__type__id=STORY_TYPES['promo'])


def test_has_from_issue_reprints(re_issue_mocks):
    i = Issue(number='1', series=ANY_SERIES)
    re_issue_mocks['fir'].count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True


def test_has_to_issue_reprints(re_issue_mocks):
    i = Issue(number='1', series=ANY_SERIES)
    re_issue_mocks['tir'].count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True


def test_delete():
    with mock.patch('%s.save' % ISSUE_PATH):
        i = Issue()
        i.reserved = True

        i.delete()

        assert i.deleted is True
        assert i.reserved is False
        i.save.assert_called_once_with()


@pytest.yield_fixture
def del_issue_mocks():
    """ Dict of mocks of things needed for deletability testing. """
    with mock.patch('%s.cover_revisions' % ISSUE_PATH) as cr_mock, \
            mock.patch('%s.variant_set' % ISSUE_PATH) as vs_mock, \
            mock.patch('%s.has_reprints' % ISSUE_PATH) as hr_mock, \
            mock.patch('%s.active_stories' % ISSUE_PATH) as as_mock:
        mocks = {
            'cr': cr_mock,
            'vs': vs_mock,
            'hr': hr_mock,
            'as': as_mock,
        }
        mocks['cr'].filter.return_value.count.return_value = 0
        mocks['vs'].filter.return_value.count.return_value = 0
        mocks['hr'].return_value = False
        mocks['as'].return_value = [mock.MagicMock(spec=Story)]
        mocks['as'].return_value[0].has_reprints.return_value = False

        yield mocks


def test_deletable(del_issue_mocks):
    i = Issue(number='1', series=ANY_SERIES)

    is_deletable = i.deletable()
    assert is_deletable is True
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)
    del_issue_mocks['as'].return_value[0].has_reprints.assert_called_once_with(
        notes=False)


def test_deletable_no_stories(del_issue_mocks):
    del_issue_mocks['as'].return_value = []

    i = Issue(number='1', series=ANY_SERIES)

    is_deletable = i.deletable()
    assert is_deletable is True
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)


def test_not_deletable_cover_revisions(del_issue_mocks):
    del_issue_mocks['cr'].filter.return_value.count.return_value = 1

    i = Issue(number='1', series=ANY_SERIES)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)


def test_not_deletable_variant_set(del_issue_mocks):
    del_issue_mocks['vs'].filter.return_value.count.return_value = 1

    i = Issue(number='1', series=ANY_SERIES)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)


def test_not_deletable_has_reprints(del_issue_mocks):
    del_issue_mocks['hr'].return_value = True

    i = Issue(number='1', series=ANY_SERIES)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)


def test_not_deletable_story_has_reprints(del_issue_mocks):
    del_issue_mocks['as'].return_value[0].has_reprints.return_value = True

    i = Issue(number='1', series=ANY_SERIES)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)
    del_issue_mocks['as'].return_value[0].has_reprints.assert_called_once_with(
        notes=False)
