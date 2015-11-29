# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import mock
import pytest

from apps.gcd.models import Country, Language, CountStats
from apps.gcd.models.issue import INDEXED


ANY_LANGUAGE = Language(id=1, code='XZZ', name='Test Language')
ANY_COUNTRY = Country(id=1, code='XYY', name='Test Country')

PUB_COUNT = 1
BRAND_COUNT = 2
IPUB_COUNT = 3
SERIES_COUNT = 4
INDEX_COUNT = 5
VARIANT_COUNT = 6
ISSUE_COUNT = 7
COVER_COUNT = 8
STORY_COUNT = 9


def test_init_stats_not_both():
    with pytest.raises(ValueError) as excinfo:
        CountStats.objects.init_stats(language=ANY_LANGUAGE,
                                      country=ANY_COUNTRY)
    assert 'either country or language stats' in unicode(excinfo.value)


@pytest.yield_fixture
def patched_filters():
    """
    Returns all of the *.objects.filter/create methods patched as a tuple.

    Order:  CountStat.create, CountStat.filter, Publisher, Brand,
            IndiciaPublisher, Series, Issue, Cover, Story
    """
    models_path = 'apps.gcd.models'
    p = '%s.countstats' % models_path

    # Note:  As single letters, "Series" is always s, "Story" is always t.
    with mock.patch('%s.CountStatsManager.filter' % p) as cs_filter, \
            mock.patch('%s.CountStatsManager.create' % p) as cs_create, \
            mock.patch('%s.Story.objects.filter' % p) as t_filter, \
            mock.patch('%s.Cover.objects.filter' % p) as c_filter, \
            mock.patch('%s.Issue.objects.filter' % p) as i_filter, \
            mock.patch('%s.Series.objects.filter' % p) as s_filter, \
            mock.patch('%s.Publisher.objects.filter' % p) as p_filter, \
            mock.patch('%s.Brand.objects.filter' % p) as b_filter, \
            mock.patch('%s.IndiciaPublisher.objects.filter' % p) as ip_filter:

        p_filter.return_value.count.return_value = PUB_COUNT
        b_filter.return_value.count.return_value = BRAND_COUNT
        ip_filter.return_value.count.return_value = IPUB_COUNT
        s_filter.return_value.count.return_value = SERIES_COUNT
        i_filter.return_value.count.return_value = ISSUE_COUNT
        i_filter.return_value.exclude.return_value.count.side_effect = (
            VARIANT_COUNT, INDEX_COUNT)
        c_filter.return_value.count.return_value = COVER_COUNT
        t_filter.return_value.count.return_value = STORY_COUNT

        yield (cs_create, cs_filter, p_filter, b_filter, ip_filter,
               s_filter, i_filter, c_filter, t_filter)


def _make_init_stats_kwargs(language=None, country=None):
        kwargs = {'deleted': False}
        if country is not None:
            kwargs['country'] = country

        p_b_ip_kwargs = kwargs.copy()

        if language is not None:
            kwargs['language'] = language

        s_kwargs = kwargs.copy()
        s_kwargs['is_comics_publication'] = True

        i_kwargs = {k if k == 'deleted' else 'series__%s' % k: v
                    for k, v in s_kwargs.iteritems()}
        c_t_kwargs = {k if k == 'deleted' else 'issue__series__%s' % k: v
                      for k, v in s_kwargs.iteritems()
                      if k != 'is_comics_publication'}

        return p_b_ip_kwargs, s_kwargs, i_kwargs, c_t_kwargs


def test_init_stats_language(patched_filters):
        (cs_create, cs_filter, p_filter, b_filter, ip_filter,
         s_filter, i_filter, c_filter, t_filter) = patched_filters

        (p_b_ip_kwargs, s_kwargs, i_kwargs,
         c_t_kwargs) = _make_init_stats_kwargs(language=ANY_LANGUAGE)

        CountStats.objects.init_stats(language=ANY_LANGUAGE)

        cs_filter.assert_called_once_with(language=ANY_LANGUAGE, country=None)
        cs_filter.return_value.delete.assert_called_once_with()
        s_filter.assert_called_once_with(**s_kwargs)

        i_filter.assert_has_calls([
            mock.call(variant_of=None, **i_kwargs),
            mock.call().count(),
            mock.call(**i_kwargs),
            mock.call().exclude(variant_of=None),
            mock.call().exclude().count(),
            mock.call(variant_of=None, **i_kwargs),
            mock.call().exclude(is_indexed=INDEXED['skeleton']),
            mock.call().exclude().count()])

        c_filter.assert_called_once_with(**c_t_kwargs)
        t_filter.assert_called_once_with(**c_t_kwargs)

        lc_args = {'language': ANY_LANGUAGE, 'country': None}
        cs_create.assert_has_calls([
            mock.call(name='series', count=SERIES_COUNT, **lc_args),
            mock.call(name='issues', count=ISSUE_COUNT, **lc_args),
            mock.call(name='variant issues', count=VARIANT_COUNT, **lc_args),
            mock.call(name='issue indexes', count=INDEX_COUNT, **lc_args),
            mock.call(name='covers', count=COVER_COUNT, **lc_args),
            mock.call(name='stories', count=STORY_COUNT, **lc_args)])


def test_init_stats_country(patched_filters):
        (cs_create, cs_filter, p_filter, b_filter, ip_filter,
         s_filter, i_filter, c_filter, t_filter) = patched_filters

        (p_b_ip_kwargs, s_kwargs, i_kwargs,
         c_t_kwargs) = _make_init_stats_kwargs(country=ANY_COUNTRY)

        CountStats.objects.init_stats(country=ANY_COUNTRY)

        cs_filter.assert_called_once_with(language=None, country=ANY_COUNTRY)
        cs_filter.return_value.delete.assert_called_once_with()

        p_filter.assert_called_once_with(**p_b_ip_kwargs)
        ip_filter.assert_called_once_with(**p_b_ip_kwargs)
        s_filter.assert_called_once_with(**s_kwargs)

        i_filter.assert_has_calls([
            mock.call(variant_of=None, **i_kwargs),
            mock.call().count(),
            mock.call(**i_kwargs),
            mock.call().exclude(variant_of=None),
            mock.call().exclude().count(),
            mock.call(variant_of=None, **i_kwargs),
            mock.call().exclude(is_indexed=INDEXED['skeleton']),
            mock.call().exclude().count()])

        c_filter.assert_called_once_with(**c_t_kwargs)
        t_filter.assert_called_once_with(**c_t_kwargs)

        # Publishers don't pass language, not even a None value.
        c_args = {'country': ANY_COUNTRY}
        lc_args = {'language': None, 'country': ANY_COUNTRY}
        cs_create.assert_has_calls([
            mock.call(name='publishers', count=PUB_COUNT, **c_args),
            mock.call(name='indicia publishers', count=IPUB_COUNT, **c_args),
            mock.call(name='series', count=SERIES_COUNT, **lc_args),
            mock.call(name='issues', count=ISSUE_COUNT, **lc_args),
            mock.call(name='variant issues', count=VARIANT_COUNT, **lc_args),
            mock.call(name='issue indexes', count=INDEX_COUNT, **lc_args),
            mock.call(name='covers', count=COVER_COUNT, **lc_args),
            mock.call(name='stories', count=STORY_COUNT, **lc_args)])


def test_init_stats_neither(patched_filters):
        (cs_create, cs_filter, p_filter, b_filter, ip_filter,
         s_filter, i_filter, c_filter, t_filter) = patched_filters

        (p_b_ip_kwargs, s_kwargs, i_kwargs,
         c_t_kwargs) = _make_init_stats_kwargs()

        CountStats.objects.init_stats()

        cs_filter.assert_called_once_with(language=None, country=None)
        cs_filter.return_value.delete.assert_called_once_with()

        p_filter.assert_called_once_with(**p_b_ip_kwargs)
        b_filter.assert_called_once_with(**p_b_ip_kwargs)
        ip_filter.assert_called_once_with(**p_b_ip_kwargs)
        s_filter.assert_called_once_with(**s_kwargs)

        i_filter.assert_has_calls([
            mock.call(variant_of=None, **i_kwargs),
            mock.call().count(),
            mock.call(**i_kwargs),
            mock.call().exclude(variant_of=None),
            mock.call().exclude().count(),
            mock.call(variant_of=None, **i_kwargs),
            mock.call().exclude(is_indexed=INDEXED['skeleton']),
            mock.call().exclude().count()])

        c_filter.assert_called_once_with(**c_t_kwargs)
        t_filter.assert_called_once_with(**c_t_kwargs)

        # Publishers don't pass language, not even a None value.
        # Brands don't pass either.
        c_args = {'country': None}
        lc_args = {'language': None, 'country': None}
        cs_create.assert_has_calls([
            mock.call(name='publishers', count=PUB_COUNT, **c_args),
            mock.call(name='brands', count=BRAND_COUNT),
            mock.call(name='indicia publishers', count=IPUB_COUNT, **c_args),
            mock.call(name='series', count=SERIES_COUNT, **lc_args),
            mock.call(name='issues', count=ISSUE_COUNT, **lc_args),
            mock.call(name='variant issues', count=VARIANT_COUNT, **lc_args),
            mock.call(name='issue indexes', count=INDEX_COUNT, **lc_args),
            mock.call(name='covers', count=COVER_COUNT, **lc_args),
            mock.call(name='stories', count=STORY_COUNT, **lc_args)])
