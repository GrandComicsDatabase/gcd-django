# -*- coding: utf-8 -*-
"""
Grouped querysets need the model's default ordering cleared, or Django folds
those fields into the GROUP BY and the counts come out wrong — hence the
.order_by() in reset_series_issue_count_cache, which rebuilds the cached
Series.issue_count.
"""

import pytest

from apps.gcd.models import Publisher, Series, Issue
from apps.stats.models import CountStats
from apps.stddata.models import Country, Language
from scripts.reset_stats import (
    main, reset_publisher_series_issue_count_cache,
    reset_series_issue_count_cache)


@pytest.fixture
def two_series(db):
    country, _ = Country.objects.get_or_create(
        code='zz', defaults={'name': 'Zedland'})
    language, _ = Language.objects.get_or_create(
        code='zz', defaults={'name': 'Zedish'})
    publisher = Publisher.objects.create(
        name='Stats Publishing', country=country, year_began=1990)

    def series(name):
        return Series.objects.create(
            name=name, sort_name=name, year_began=1990, country=country,
            language=language, publisher=publisher,
            is_comics_publication=True, has_gallery=False)

    return series('Alpha'), series('Beta')


def _issue(series, sort_code, **kwargs):
    return Issue.objects.create(
        number=str(sort_code), series=series, sort_code=sort_code,
        **kwargs)


@pytest.mark.django_db
def test_rebuild_counts_base_and_cross_series_variants(two_series):
    alpha, beta = two_series
    base = _issue(alpha, 1)
    _issue(alpha, 2)                    # second base issue: counted
    _issue(alpha, 3, variant_of=base)   # same-series variant: not counted
    _issue(beta, 1, variant_of=base)    # cross-series variant: counted
    _issue(beta, 2, deleted=True)       # deleted: not counted

    # Corrupt the cached counts; the rebuild must repair them.
    Series.objects.update(issue_count=99)

    reset_series_issue_count_cache()

    alpha.refresh_from_db()
    beta.refresh_from_db()
    assert alpha.issue_count == 2
    assert beta.issue_count == 1


@pytest.mark.django_db
def test_rebuild_zeroes_series_without_issues(two_series):
    alpha, _ = two_series
    Series.objects.update(issue_count=7)

    reset_series_issue_count_cache()

    alpha.refresh_from_db()
    assert alpha.issue_count == 0


@pytest.mark.django_db
def test_main_rebuilds_countstats(two_series):
    CountStats.objects.all().delete()

    main()

    assert CountStats.objects.exists()


def _series_like(other, name, **kwargs):
    """Create a series with the country and language of another one."""
    return Series.objects.create(
        name=name, sort_name=name, year_began=1990, country=other.country,
        language=other.language, has_gallery=False, **kwargs)


@pytest.mark.django_db
def test_recount_publisher_series_and_issues(two_series):
    """
    Each publisher gets what the approvals add up: its series that are
    not deleted, and the base issues of those that are comics publications.
    """
    alpha, beta = two_series
    publisher = alpha.publisher
    gamma = _series_like(alpha, 'Gamma', publisher=publisher,
                         is_comics_publication=False)
    _series_like(alpha, 'Delta', publisher=publisher,
                 is_comics_publication=True, deleted=True)
    base = _issue(alpha, 1)
    _issue(alpha, 2)                    # base issue: counted
    _issue(alpha, 3, variant_of=base)   # same-series variant: not counted
    _issue(alpha, 4, deleted=True)      # deleted: not counted
    _issue(beta, 1)                     # base issue: counted
    _issue(beta, 2, variant_of=base)    # cross-series variant: not counted
    _issue(gamma, 1)                    # not a comics publication
    other = Publisher.objects.create(
        name='Other Publishing', country=alpha.country, year_began=1990)
    _issue(_series_like(alpha, 'Epsilon', publisher=other,
                        is_comics_publication=True), 1)

    # Corrupt the cached counts; the recount must repair them.
    Publisher.objects.update(series_count=99, issue_count=99)

    reset_publisher_series_issue_count_cache()

    publisher.refresh_from_db()
    other.refresh_from_db()
    assert (publisher.series_count, publisher.issue_count) == (3, 3)
    assert (other.series_count, other.issue_count) == (1, 1)
    # The same totals as the stat_counts() that the approvals add up.
    counts = [series.stat_counts() for series in publisher.series_set.all()]
    assert publisher.series_count == sum(
        c.get('series', 0) + c.get('publisher series', 0) for c in counts)
    assert publisher.issue_count == sum(c.get('issues', 0) for c in counts)


@pytest.mark.django_db
def test_recount_zeroes_publisher_without_series(two_series):
    """A publisher without series gets 0 for both counts."""
    alpha, _ = two_series
    empty = Publisher.objects.create(
        name='Empty Publishing', country=alpha.country, year_began=1990)
    Publisher.objects.update(series_count=7, issue_count=7)

    reset_publisher_series_issue_count_cache()

    empty.refresh_from_db()
    assert (empty.series_count, empty.issue_count) == (0, 0)
