# -*- coding: utf-8 -*-

import pytest
import mock

from apps.oi.models import SeriesRevision


@pytest.mark.django_db
def test_create_add_revision(any_added_series_rev, series_add_values,
                             keywords, any_changeset):
    sr = any_added_series_rev

    for k, v in series_add_values.iteritems():
        assert getattr(sr, k) == v

    assert sr.series is None

    assert sr.reservation_requested is False
    assert sr.changeset == any_changeset
    assert sr.date_inferred is False

    assert sr.source is None
    assert sr.source_name == 'series'

    # Simple version of this for mocking.  Real article testing elsewhere.
    sort_name = sr.name[sr.name.index(' ') + 1:]
    with mock.patch('apps.oi.models.update_count') as updater, \
            mock.patch('apps.oi.models.remove_leading_article') as remover:
        remover.return_value = sort_name
        sr.commit_to_display()
    assert updater.called_once_with('series', 1,
                                    language=sr.language, country=sr.country)

    assert sr.series is not None
    assert sr.source is sr.series

    for k, v in series_add_values.iteritems():
        if k == 'keywords':
            kws = [k for k in sr.publisher.keywords.names()]
            kws.sort()
            assert kws == keywords['list']
        else:
            assert getattr(sr.series, k) == v

    assert remover.called_once_with(sr.name)
    assert sr.series.sort_name == sort_name
    assert sr.series.issue_count == 0


@pytest.mark.django_db
def test_create_add_rev_no_leading_article(any_added_series_rev):
    sr = any_added_series_rev
    sr.leading_article = False
    sr.save()

    with mock.patch('apps.oi.models.update_count'), \
            mock.patch('apps.oi.models.remove_leading_article') as remover:
        # Not testing actual remover logic here, just that it's not called.
        remover.return_value = sr.name
        sr.commit_to_display()

    # Assume everything else worked as tested in the general add case.
    assert remover.called is False
    assert sr.series.name == sr.name
    assert sr.series.sort_name == sr.name


def test_form_fields(series_form_fields):
    # TODO: See TODO comment about the instance check for changed publisher.
    assert SeriesRevision.form_field_list() == series_form_fields
