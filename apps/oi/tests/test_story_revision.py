# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from apps.oi.models import StoryRevision


def test_stats_category_field_tuples():
    assert StoryRevision._get_stats_category_field_tuples() == {
        ('issue', 'series', 'country'),
        ('issue', 'series', 'language'),
    }
