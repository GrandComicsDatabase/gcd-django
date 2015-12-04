# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from django.db.models import QuerySet

from apps.gcd.models import Series, Issue, Story, Cover
from apps.gcd.models.issue import INDEXED
from apps.gcd.models.story import STORY_TYPES

# TODO: We really shouldn't be depending on the OI here.
from apps.oi import states


ISSUE_PATH = 'apps.gcd.models.issue.Issue'


@pytest.fixture
def any_series():
    """ Unsaved comics publication series with valid name and year began. """
    return Series(name='Test Series', year_began=1940,
                  is_comics_publication=True)


@pytest.yield_fixture
def image_and_content_type():
    """
    Returns a 4-tuple of mocks for use in testing image properties.

    Position 0: Mock Image.objects
    Position 1: Mock Image query set, returned from Image.objects.filter
    Position 2: Mock ContentType.objects
    Position 3: Mock ContentType returned from
                ContentType.objects.get_for_model
    """
    with mock.patch('apps.gcd.models.issue.Image.objects') as image_obj_mock, \
            mock.patch('apps.gcd.models.issue.ContentType.objects') \
            as ct_obj_mock:
        image_qs = mock.MagicMock(spec=QuerySet)
        image_obj_mock.filter.return_value = image_qs
        ct_mock = mock.MagicMock()
        ct_obj_mock.get_for_model.return_value = ct_mock
        yield image_obj_mock, image_qs, ct_obj_mock, ct_mock


def test_indicia_image(any_series, image_and_content_type):
        image_obj_mock, image_qs, ct_obj_mock, ct_mock = image_and_content_type

        i = Issue(number='1', series=any_series)
        img = i.indicia_image
        assert img == image_qs.get.return_value
        image_obj_mock.filter.assert_called_once_with(object_id=i.id,
                                                      deleted=False,
                                                      content_type=ct_mock,
                                                      type__id=1)
        image_qs.get.assert_called_once_with()


def test_no_indicia_image(any_series, image_and_content_type):
        image_obj_mock, image_qs, ct_obj_mock, ct_mock = image_and_content_type

        image_obj_mock.filter.return_value = []
        i = Issue(number='1', series=any_series)
        assert i.indicia_image is None


def test_soo_image(any_series, image_and_content_type):
        image_obj_mock, image_qs, ct_obj_mock, ct_mock = image_and_content_type

        i = Issue(number='1', series=any_series)
        img = i.soo_image
        assert img == image_qs.get.return_value
        image_obj_mock.filter.assert_called_once_with(object_id=i.id,
                                                      deleted=False,
                                                      content_type=ct_mock,
                                                      type__id=2)
        image_qs.get.assert_called_once_with()


def test_no_soo_image(any_series, image_and_content_type):
        image_obj_mock, image_qs, ct_obj_mock, ct_mock = image_and_content_type

        image_obj_mock.filter.return_value = []
        i = Issue(number='1', series=any_series)
        assert i.soo_image is None


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


def test_can_upload_variants(any_series):
    with mock.patch('%s.revisions' % ISSUE_PATH) as rev_mock, \
            mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = True
        rev_mock.filter.return_value.count.return_value = 0
        i = Issue(number='1', series=any_series)

        can_upload_variants = i.can_upload_variants()
        assert bool(can_upload_variants) is True
        rev_mock.filter.assert_called_once_with(
            changeset__state__in=states.ACTIVE, deleted=True)


def test_cant_upload_variants_no_covers(any_series):
    with mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = False
        i = Issue(number='1', series=any_series)

        can_upload_variants = i.can_upload_variants()
        assert bool(can_upload_variants) is False


def test_cant_upload_variants_active_revisions(any_series):
    with mock.patch('%s.revisions' % ISSUE_PATH) as rev_mock, \
            mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = True
        rev_mock.filter.return_value.count.return_value = 1
        i = Issue(number='1', series=any_series)

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


def test_no_reprints(any_series, re_issue_mocks):
    i = Issue(number='1', series=any_series)
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is False
    re_issue_mocks['tr'].exclude.assert_called_once_with(
        target__type__id=STORY_TYPES['promo'])


def test_has_from_reprints(any_series, re_issue_mocks):
    i = Issue(number='1', series=any_series)
    re_issue_mocks['fr'].count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True


def test_has_to_reprints(any_series, re_issue_mocks):
    i = Issue(number='1', series=any_series)
    re_issue_mocks['tr'].exclude.return_value.count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True
    re_issue_mocks['tr'].exclude.assert_called_once_with(
        target__type__id=STORY_TYPES['promo'])


def test_has_from_issue_reprints(any_series, re_issue_mocks):
    i = Issue(number='1', series=any_series)
    re_issue_mocks['fir'].count.return_value = 1
    has_reprints = i.has_reprints()
    assert bool(has_reprints) is True


def test_has_to_issue_reprints(any_series, re_issue_mocks):
    i = Issue(number='1', series=any_series)
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


def test_deletable(any_series, del_issue_mocks):
    i = Issue(number='1', series=any_series)

    is_deletable = i.deletable()
    assert is_deletable is True
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)
    del_issue_mocks['as'].return_value[0].has_reprints.assert_called_once_with(
        notes=False)


def test_deletable_no_stories(any_series, del_issue_mocks):
    del_issue_mocks['as'].return_value = []

    i = Issue(number='1', series=any_series)

    is_deletable = i.deletable()
    assert is_deletable is True
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)


def test_not_deletable_cover_revisions(any_series, del_issue_mocks):
    del_issue_mocks['cr'].filter.return_value.count.return_value = 1

    i = Issue(number='1', series=any_series)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)


def test_not_deletable_variant_set(any_series, del_issue_mocks):
    del_issue_mocks['vs'].filter.return_value.count.return_value = 1

    i = Issue(number='1', series=any_series)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)


def test_not_deletable_has_reprints(any_series, del_issue_mocks):
    del_issue_mocks['hr'].return_value = True

    i = Issue(number='1', series=any_series)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)


def test_not_deletable_story_has_reprints(any_series, del_issue_mocks):
    del_issue_mocks['as'].return_value[0].has_reprints.return_value = True

    i = Issue(number='1', series=any_series)

    is_deletable = i.deletable()
    assert is_deletable is False
    del_issue_mocks['cr'].filter.assert_called_once_with(
        changeset__state__in=states.ACTIVE)
    del_issue_mocks['vs'].filter.assert_called_once_with(deleted=False)
    del_issue_mocks['as'].return_value[0].has_reprints.assert_called_once_with(
        notes=False)


def test_active_stories(any_series):
    with mock.patch('%s.story_set' % ISSUE_PATH) as ss_mock:
        qs = mock.MagicMock(spec=QuerySet)
        ss_mock.exclude.return_value = qs
        i = Issue(number='1', series=any_series)

        active_stories = i.active_stories()
        assert active_stories is qs
        ss_mock.exclude.assert_called_once_with(deleted=True)


def test_active_variants(any_series):
    with mock.patch('%s.variant_set' % ISSUE_PATH) as vs_mock:
        qs = mock.MagicMock(spec=QuerySet)
        vs_mock.exclude.return_value = qs
        i = Issue(number='1', series=any_series)

        active_variants = i.active_variants()
        assert active_variants is qs
        vs_mock.exclude.assert_called_once_with(deleted=True)


def test_has_covers(any_series):
    with mock.patch('%s.can_have_cover' % ISSUE_PATH) as cs_mock, \
            mock.patch('%s.active_covers' % ISSUE_PATH) as ac_mock:

        cs_mock.return_value = True
        ac_mock.return_value.count.return_value = 1
        i = Issue(number='1', series=any_series)

        assert i.has_covers()

        ac_mock.return_value.count.return_value = 0

        assert not i.has_covers()

        cs_mock.return_value = False

        assert not i.has_covers()

        ac_mock.return_value.count.return_value = 1

        assert not i.has_covers()


def test_can_have_cover(any_series):
    i = Issue(number='1', series=any_series)
    i.series.is_comics_publication = True
    i.is_indexed = INDEXED['skeleton']

    assert i.can_have_cover()

    i.series.is_comics_publication = False

    assert not i.can_have_cover()

    i.is_indexed = INDEXED['full']

    assert i.can_have_cover()

    i.is_indexed = INDEXED['ten_percent']

    assert i.can_have_cover()

    i.is_indexed = INDEXED['partial']

    assert not i.can_have_cover()


def test_active_covers(any_series):
    with mock.patch('%s.cover_set' % ISSUE_PATH) as cs_mock:
        qs = mock.MagicMock(spec=QuerySet)
        cs_mock.exclude.return_value = qs
        i = Issue(number='1', series=any_series)

        active_covers = i.active_covers()
        assert active_covers is qs
        cs_mock.exclude.assert_called_once_with(deleted=True)


def test_variant_covers_variant_of(any_series):
    with mock.patch('apps.gcd.models.cover.Cover.objects') as cobj_mock, \
            mock.patch('%s.variant_of' % ISSUE_PATH) as vo_mock:

        vo_mock.variant_set.exclude.return_value \
                           .exclude.return_value \
                           .values_list.return_value = [1, 2]

        cobj_qs_mock = mock.MagicMock()
        cobj_mock.filter.return_value.exclude.return_value = cobj_qs_mock

        ac_qs_mock = mock.MagicMock(spec=QuerySet)
        vo_mock.active_covers.return_value = ac_qs_mock

        i = Issue(number='1', series=any_series)
        vc = i.variant_covers()

        vo_mock.variant_set.exclude.assert_called_once_with(id=i.id)
        vo_mock.variant_set.exclude.return_value \
                           .exclude.assert_called_once_with(deleted=True)
        vo_mock.variant_set.exclude.return_value \
                           .exclude.return_value \
                           .values_list.assert_called_once_with('id',
                                                                flat=True)
        cobj_mock.filter.assert_called_once_with(issue__id__in=[1, 2])
        cobj_mock.filter.return_value \
                 .exclude.assert_called_once_with(deleted=True)
        # __ior__ implements |=
        cobj_qs_mock.__ior__.assert_called_once_with(ac_qs_mock)
        assert vc == cobj_qs_mock.__ior__.return_value


def test_variant_covers_base(any_series):
    with mock.patch('apps.gcd.models.cover.Cover.objects') as cobj_mock, \
            mock.patch('%s.variant_set' % ISSUE_PATH) as vs_mock:

        vs_mock.exclude.return_value.values_list.return_value = [3, 4, 5]

        cobj_qs_mock = mock.MagicMock()
        cobj_mock.filter.return_value.exclude.return_value = cobj_qs_mock

        i = Issue(variant_of=None, number='1', series=any_series)
        vc = i.variant_covers()

        vs_mock.exclude.assert_called_once_with(deleted=True)
        vs_mock.exclude.return_value \
               .values_list.assert_called_once_with('id', flat=True)

        cobj_mock.filter.assert_called_once_with(issue__id__in=[3, 4, 5])
        cobj_mock.filter.return_value \
                 .exclude.assert_called_once_with(deleted=True)
        # __ior__ implements |=
        assert not cobj_qs_mock.__ior__.called
        assert vc == cobj_qs_mock


def test_shown_covers(any_series):
    with mock.patch('%s.active_covers' % ISSUE_PATH) as ac_mock, \
            mock.patch('%s.variant_covers' % ISSUE_PATH) as vc_mock:

        v1, v2, v3, v4, v5 = [mock.MagicMock(spec=Cover) for x in range(0, 5)]
        # Should really be QuerySets and not lists, but close enough for
        # unit testing purposes.
        ac_mock.return_value = [v1, v2]
        vc_mock.return_value = [v3, v4, v5]

        i = Issue(number='1', series=any_series)
        first, second = i.shown_covers()
        assert first == [v1, v2]
        assert second == [v3, v4, v5]


@pytest.yield_fixture
def stat_count_mocks():
    """
    Yields a 2-tuple of mocks for testing statistics.

    Position 0: Issue.active_stories() with count set to 0
    Position 1: Issue.active_covers() with count set to 0
    """
    with mock.patch('%s.active_stories' % ISSUE_PATH) as as_mock, \
            mock.patch('%s.active_covers' % ISSUE_PATH) as ac_mock:
        as_mock.return_value.count.return_value = 0
        ac_mock.return_value.count.return_value = 0
        yield as_mock, ac_mock


def test_stat_counts_base_skeleton(any_series, stat_count_mocks):
    i = Issue(number='1',
              series=any_series,
              is_indexed=INDEXED['skeleton'])
    counts = i.stat_counts()
    assert counts == {
        'issues': 1,
        'covers': 0,
        'stories': 0,
    }


def test_stat_counts_base_indexed_covers_stories(any_series, stat_count_mocks):
    as_mock, ac_mock = stat_count_mocks
    as_mock.return_value.count.return_value = 10
    ac_mock.return_value.count.return_value = 2

    i = Issue(number='1',
              series=any_series,
              is_indexed=INDEXED['full'])
    counts = i.stat_counts()
    assert counts == {
        'issues': 1,
        'issue indexes': 1,
        'covers': 2,
        'stories': 10,
    }


def test_stat_counts_variant_partial(any_series, stat_count_mocks):
    i = Issue(number='1',
              series=any_series,
              is_indexed=INDEXED['partial'],
              variant_of_id=1234)

    counts = i.stat_counts()
    assert counts == {
        'variant issues': 1,
        'issue indexes': 1,
        'covers': 0,
        'stories': 0,
    }


def test_stat_counts_non_comics(any_series, stat_count_mocks):
    as_mock, ac_mock = stat_count_mocks
    as_mock.return_value.count.return_value = 10
    ac_mock.return_value.count.return_value = 2

    any_series.is_comics_publication = False
    i = Issue(number='1',
              series=any_series)
    counts = i.stat_counts()
    assert counts == {
        'covers': 2,
        'stories': 10,
    }
