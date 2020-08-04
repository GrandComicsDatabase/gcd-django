# -*- coding: utf-8 -*-

import pytest

from django import db

from apps.oi.models import RevisionLock
from apps.gcd.models import Publisher, IndiciaPublisher
from apps.stddata.models import Country

@pytest.fixture
def lockables():
    """
    3-tuple of display objects of varying types and database ids.

    0.  A publisher, id=1
    1.  A different publisher, id=2
    2.  An indicia publisher id=1 (same as the publisher at position 0)
    """
    country, created = Country.objects.get_or_create(code='US')

    pub1, created = Publisher.objects.get_or_create(id=1,
                                                    name='Test Publisher',
                                                    country=country)
    pub2, created = Publisher.objects.get_or_create(id=2,
                                                    name='Other Publisher',
                                                    country=country)
    ipub1, created = IndiciaPublisher.objects.get_or_create(id=1,
                                                            parent=pub1,
                                                            name='Test IndPub',
                                                            country=country)
    return pub1, pub2, ipub1

@pytest.mark.django_db
def test_unique_together_configured_correctly(lockables):
    pub1, pub2, ipub1 = lockables

    good_lock = RevisionLock(locked_object=pub1)
    good_lock.save()
    assert good_lock.locked_object == pub1

    # Try one of the same type, but different database id.
    second_lock = RevisionLock(locked_object=pub2)
    second_lock.save()
    assert second_lock.locked_object == pub2

    # Try one of a different type but the same database id.
    third_lock = RevisionLock(locked_object=ipub1)
    third_lock.save()
    assert third_lock.locked_object == ipub1

    # Try locking an already locked object.
    with pytest.raises(db.IntegrityError) as excinfo:
        bad_lock = RevisionLock(locked_object=pub1)
        bad_lock.save()
    assert 'Duplicate entry' in str(excinfo.value)
