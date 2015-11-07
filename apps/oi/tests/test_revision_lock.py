# -*- coding: utf-8 -*-

import pytest

from django import db

from apps.oi.models import RevisionLock
from apps.gcd.models import Publisher, Country


@pytest.fixture
def display_obj():
    """
    Generic test Display object.  Publisher has the least dependencies.
    """
    country = Country(code='XZZ', name='Test Country')
    country.save()

    pub = Publisher(name='Test Publisher', country=country)
    pub.save()
    return pub


@pytest.mark.django_db
def test_unique_together_configured_correctly(display_obj):
    good_lock = RevisionLock(locked_object=display_obj)
    good_lock.save()
    assert good_lock.locked_object == display_obj

    with pytest.raises(db.IntegrityError) as excinfo:
        bad_lock = RevisionLock(locked_object=display_obj)
        bad_lock.save()
    assert u'Duplicate entry' in unicode(excinfo.value)
