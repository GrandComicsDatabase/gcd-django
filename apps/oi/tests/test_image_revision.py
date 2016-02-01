# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from apps.oi.models import Revision, ImageRevision


def test_excluded_fields():
    assert ImageRevision._get_excluded_field_names() == {
        'image_file',
        'scaled_image',
        'marked',
    } | Revision._get_excluded_field_names()
