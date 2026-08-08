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
from scripts.reset_stats import main, reset_series_issue_count_cache


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
