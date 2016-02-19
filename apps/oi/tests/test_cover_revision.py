# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from apps.oi.models import Revision, CoverRevision


def test_excluded_fields():
    assert CoverRevision._get_excluded_field_names() == {
        'is_wraparound',
        'front_left',
        'front_right',
        'front_top',
        'front_bottom',
    } | Revision._get_excluded_field_names()


def test_stats_category_field_tuples():
    assert CoverRevision._get_stats_category_field_tuples() == {
        ('issue', 'series', 'country'),
        ('issue', 'series', 'language'),
    }
