# -*- coding: utf-8 -*-


import pytest

from apps.oi.models import (PublisherRevision, IndiciaPublisherRevision,
                            BrandGroupRevision, BrandRevision)


@pytest.mark.parametrize('has_country, rev_class',
                         [(True, PublisherRevision),
                          (True, IndiciaPublisherRevision),
                          (False, BrandGroupRevision),
                          (False, BrandRevision)])
def test_stats_category_field_tuples(has_country, rev_class):
    tuples = rev_class._get_stats_category_field_tuples()
    assert tuples == ({('country',)} if has_country else set())
