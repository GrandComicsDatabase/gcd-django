# -*- coding: utf-8 -*-



import mock
import pytest

from django.db.models import QuerySet

from apps.gcd.models import Series, Issue, Cover
from apps.gcd.models.issue import INDEXED
from apps.gcd.models.story import STORY_TYPES


ISSUE_PATH = 'apps.gcd.models.issue.Issue'
STORY_PATH = 'apps.gcd.models.story.Story'
REVMGR_PATH = 'apps.oi.models.RevisionManager'


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
            mock.patch('%s.active_variants' % ISSUE_PATH,
                       spec=QuerySet) as vs_mock:

        v1, v2, v3, v4 = [mock.MagicMock(spec=Issue) for x in range(0, 4)]

        vo_mock.active_variants.return_value.exclude.return_value = [v1, v2]
        vs_mock.return_value = [v3, v4]

        i = Issue()
        assert i.other_variants() == [v1, v2]
        i.variant_of.active_variants.return_value.exclude\
                    .assert_called_once_with(id=i.id)
        i.variant_of.active_variants.assert_called_once_with()

        i.variant_of = None
        assert i.other_variants() == [v3, v4]
        i.active_variants.assert_called_once_with()
        i.active_variants.assert_called_once_with()


def test_can_upload_variants(any_series):
    with mock.patch('%s.active_set' % REVMGR_PATH) as rev_mock, \
            mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = True
        rev_mock.return_value.filter.return_value.exists.return_value = False
        i = Issue(number='1', series=any_series)

        can_upload_variants = i.can_upload_variants()
        assert can_upload_variants is True


def test_cant_upload_variants_no_covers(any_series):
    with mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = False
        i = Issue(number='1', series=any_series)

        can_upload_variants = i.can_upload_variants()
        assert can_upload_variants is False


def test_cant_upload_variants_active_revisions(any_series):
    with mock.patch('%s.active_set' % REVMGR_PATH) as rev_mock, \
            mock.patch('%s.has_covers' % ISSUE_PATH) as hc_mock:
        hc_mock.return_value = True
        rev_mock.return_value.exists.return_value = True
        i = Issue(number='1', series=any_series)

        can_upload_variants = i.can_upload_variants()
        assert can_upload_variants is False


#@pytest.yield_fixture
#def re_issue_mocks(any_series):
    #with mock.patch('%s.from_all_reprints' % ISSUE_PATH) as from_mock, \
            #mock.patch('%s.to_all_reprints' % ISSUE_PATH) as to_mock:

        #from_mock.exists.return_value = False
        #to_mock.exclude.return_value.exists.return_value = False

        #yield from_mock, to_mock, Issue(number='1', series=any_series)


#def test_from_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks
    #r = i.from_reprints
    #assert r == from_mock.exclude.return_value
    #from_mock.exclude.assert_called_once_with(origin=None)


#def test_to_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks
    #r = i.to_reprints
    #assert r == to_mock.exclude.return_value
    #to_mock.exclude.assert_called_once_with(target=None)


#def test_from_issue_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks
    #r = i.from_issue_reprints
    #assert r == from_mock.filter.return_value
    #from_mock.filter.assert_called_once_with(origin=None)


#def test_to_issue_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks
    #r = i.to_issue_reprints
    #assert r == to_mock.filter.return_value
    #to_mock.filter.assert_called_once_with(target=None)


#def test_no_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks

    #has_reprints = i.has_reprints()

    #assert has_reprints is False
    #to_mock.exclude.assert_called_once_with(
        #target__type__id=STORY_TYPES['promo'])


#def test_has_from_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks

    #from_mock.exists.return_value = True
    #has_reprints = i.has_reprints()

    #assert has_reprints is True


#def test_has_to_reprints(re_issue_mocks):
    #from_mock, to_mock, i = re_issue_mocks

    #to_mock.exclude.return_value.exists.return_value = True
    #has_reprints = i.has_reprints()

    #assert has_reprints is True
    #to_mock.exclude.assert_called_once_with(
        #target__type__id=STORY_TYPES['promo'])


def test_delete():
    with mock.patch('%s.save' % ISSUE_PATH):
        i = Issue()

        i.delete()

        assert i.deleted is True
        i.save.assert_called_once_with()


@pytest.yield_fixture
def del_issue_mocks():
    """ Dict of mocks of things needed for deletability testing. """
    with mock.patch('%s.has_reprints' % ISSUE_PATH) as issue_hr_mock, \
            mock.patch('%s.active_stories' % ISSUE_PATH) as as_mock, \
            mock.patch('%s.origin_reprint_revisions' %
                       ISSUE_PATH) as issue_or_mock, \
            mock.patch('%s.target_reprint_revisions' %
                       ISSUE_PATH) as issue_tr_mock, \
            mock.patch('%s.has_variants' % ISSUE_PATH) as hv_mock, \
            mock.patch('%s.cover_revisions' % ISSUE_PATH) as cr_mock, \
            mock.patch('%s.variant_revisions' % ISSUE_PATH) as vr_mock:

        # Not using spec=Story, b/c Django models do weird dynamic field
        # stuff with reverse relations that confuses mock's spec system.
        # These tests don't rely on the spec functionality anyway.
        story = mock.MagicMock()
        mocks = {
            'hv': hv_mock,
            'cr': cr_mock,
            'vr': vr_mock,
            'as': as_mock,
            'issue_hr': issue_hr_mock,
            'story_hr': story.has_reprints,
            'issue_or': issue_or_mock,
            'issue_tr': issue_tr_mock,
            'story_or': story.origin_reprint_revisions,
            'story_tr': story.target_reprint_revisions,
        }
        mocks['hv'].return_value = False
        mocks['cr'].active_set.return_value.exists.return_value = False
        mocks['vr'].active_set.return_value.exists.return_value = False
        mocks['as'].return_value = [story]
        mocks['issue_hr'].return_value = False
        mocks['story_hr'].return_value = False
        mocks['issue_or'].active_set.return_value.exists.return_value = False
        mocks['issue_tr'].active_set.return_value.exists.return_value = False
        mocks['story_or'].active_set.return_value.exists.return_value = False
        mocks['story_tr'].active_set.return_value.exists.return_value = False

        yield mocks


def test_has_no_dependents(any_series, del_issue_mocks):
    i = Issue(number='1', series=any_series)

    has_dependents = i.has_dependents()
    assert has_dependents is False

    # For this basic positive test case only, check that the right calls
    # were made.  We don't need to do this every time, as from this point
    # on, all we change are return values so clearly things still get called.
    del_issue_mocks['hv'].assert_called_once_with()
    del_issue_mocks['issue_hr'].assert_called_once_with(ignore=None)
    del_issue_mocks['story_hr'].assert_called_once_with(notes=False)
    del_issue_mocks['issue_or'].active_set.return_value \
                               .exists.assert_called_once_with()
    del_issue_mocks['issue_tr'].active_set.return_value \
                               .exists.assert_called_once_with()
    del_issue_mocks['story_or'].active_set.return_value \
                               .exists.assert_called_once_with()
    del_issue_mocks['story_tr'].active_set.return_value \
                               .exists.assert_called_once_with()


def test_has_no_dependents_no_stories(any_series, del_issue_mocks):
    del_issue_mocks['as'].return_value = []

    i = Issue(number='1', series=any_series)

    has_dependents = i.has_dependents()
    assert has_dependents is False


@pytest.mark.parametrize('which_exists', ['hv', 'issue_hr', 'story_hr'])
def test_has_dependents_variant_set(any_series, del_issue_mocks, which_exists):
    del_issue_mocks[which_exists].return_value = True

    i = Issue(number='1', series=any_series)

    has_dependents = i.has_dependents()
    assert has_dependents is True


@pytest.mark.parametrize('which_exists', ['issue_or', 'issue_tr', 'cr',
                                          'story_or', 'story_tr', 'vr'])
def test_has_dependents_has_revisions(any_series, del_issue_mocks,
                                      which_exists):
    del_issue_mocks[which_exists].active_set.return_value \
                                 .exists.return_value = True
    i = Issue(number='1', series=any_series)

    has_dependents = i.has_dependents()
    assert has_dependents is True


def test_active_stories(any_series):
    with mock.patch('%s.story_set' % ISSUE_PATH) as ss_mock:
        qs = mock.MagicMock(spec=QuerySet)
        ss_mock.exclude.return_value = qs
        i = Issue(number='1', series=any_series)

        active_stories = i.active_stories()
        assert active_stories is qs


def test_active_variants(any_series):
    with mock.patch('%s.variant_set' % ISSUE_PATH) as vs_mock:
        qs = mock.MagicMock(spec=QuerySet)
        vs_mock.exclude.return_value = qs
        i = Issue(number='1', series=any_series)

        active_variants = i.active_variants()
        assert active_variants is qs
        vs_mock.exclude.assert_called_once_with(deleted=True)


@pytest.mark.parametrize('result', [True, False])
def test_has_variants(any_series, result):
    with mock.patch('%s.active_variants' % ISSUE_PATH) as vs_mock:
        vs_mock.return_value.exists.return_value = result
        i = Issue(number='1', series=any_series)

        assert i.has_variants() is result


@pytest.mark.parametrize('can_have, active', [
    (True, True), (True, False), (False, True), (False, False)])
def test_has_covers(any_series, can_have, active):
    with mock.patch('%s.can_have_cover' % ISSUE_PATH) as cs_mock, \
            mock.patch('%s.active_covers' % ISSUE_PATH) as ac_mock:

        cs_mock.return_value = can_have
        ac_mock.return_value.exists.return_value = active
        i = Issue(number='1', series=any_series)

        has = i.has_covers()
        assert has is all((can_have, active))


@pytest.mark.parametrize('is_comics, is_indexed, result', [
    # Always true if comics, sometimes true based on indexed if not comics.
    (True, INDEXED['skeleton'], True),
    (True, INDEXED['full'], True),
    (True, INDEXED['ten_percent'], True),
    (True, INDEXED['partial'], True),
    (False, INDEXED['skeleton'], False),
    (False, INDEXED['full'], True),
    (False, INDEXED['ten_percent'], True),
    (False, INDEXED['partial'], False)])
def test_can_have_cover(any_series, is_comics, is_indexed, result):
    i = Issue(number='1', series=any_series)
    i.series.is_comics_publication = is_comics
    i.is_indexed = is_indexed

    can = i.can_have_cover()
    assert can is result


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

        vo_mock.active_variants.return_value.exclude.return_value \
                               .values_list.return_value = [1, 2]

        cobj_qs_mock = mock.MagicMock()
        cobj_mock.filter.return_value.exclude.return_value = cobj_qs_mock

        ac_qs_mock = mock.MagicMock(spec=QuerySet)
        vo_mock.active_covers.return_value = ac_qs_mock

        i = Issue(number='1', series=any_series)
        vc = i.variant_covers()

        vo_mock.active_variants.return_value\
                               .exclude.assert_called_once_with(id=i.id)
        vo_mock.active_variants.return_value\
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
        'series issues': 1,
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
        'series issues': 1,
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
        'series issues': 1,
        'covers': 2,
        'stories': 10,
    }


def test_stat_counts_deleted(any_series):
    i = Issue(number='1', series=any_series)
    i.deleted = True
    assert i.stat_counts() == {}
