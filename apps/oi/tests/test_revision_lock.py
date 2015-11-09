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
    country, created = Country.objects.get_or_create(code='US')

    pub, created = Publisher.objects.get_or_create(name='Test Publisher',
                                                   country=country)
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
