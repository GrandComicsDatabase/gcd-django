# -*- coding: utf-8 -*-


import pytest

from django.db import models
from django.contrib.auth.models import User
from taggit.managers import TaggableManager

from apps.gcd.models.gcddata import GcdData
from apps.oi.models import Revision


# Make a non-abstract classes that act like Revisions, but con be
# instantiated (otherwise the OneToOneField has problems) and can
# have a manager, i.e. DummyRevision.objects.
#
# These should not be needed in other test modules as they should
# all instantiate the proper concrete revision, even if they are
# not saving it to the database.

# Make some dummy data objects to correspond to the dummy revisions.
# These need to go first so that we can set source_class for the revisions.
class Dummy(GcdData):
    class Meta:
        app_label = 'gcd'

    _update_stats = True

    # Note that GcdData brings in some excluded fields.
    i = models.IntegerField()
    b = models.BooleanField(default=False)
    f = models.ForeignKey('gcd.OtherDummy')
    o = models.OneToOneField('gcd.OtherDummy')
    m = models.ManyToManyField('gcd.OtherDummy')
    z = models.DecimalField()           # used to test meta fields
    x = models.BooleanField(default=False)           # type mismatch with revision
    c = models.CharField(max_length=255)              # Not present in Revision
    keywords = TaggableManager()        # keywords must be called 'keywords'


class OtherDummy(GcdData):
    class Meta:
        app_label = 'gcd'

    _update_stats = True

    name = models.CharField(max_length=255)


class DummyRevision(Revision):
    class Meta:
        app_label = 'oi'

    dummy = models.ForeignKey('gcd.Dummy', null=True)

    # Note that the 'deleted' excluded field is defined in Revision.
    i = models.IntegerField()
    b = models.BooleanField()
    f = models.ForeignKey('gcd.OtherDummy')
    o = models.OneToOneField('gcd.OtherDummy')
    m = models.ManyToManyField('gcd.OtherDummy')
    z = models.DecimalField()           # used to test meta fields
    x = models.CharField()              # type mismatch with data object
    y = models.BooleanField()           # Not present on data object
    keywords = models.TextField()       # keywords field on revision is text

    source_name = 'Dummy'
    source_class = Dummy

    @property
    def source(self):
        return self.dummy

    @source.setter
    def source(self, value):
        self.dummy = value

    @classmethod
    def _get_meta_field_names(cls):
        return {'z'}

    @classmethod
    def _get_parent_field_tuples(cls):
        return {('f',), ('o',), ('m',)}

    @classmethod
    def _get_major_flag_field_tuples(cls):
        return {('b',)}


# A revision with a source but no parent / conditional / etc. fields declared.
class OtherDummyRevision(Revision):
    class Meta:
        app_label = 'oi'

    other_dummy = models.ForeignKey(OtherDummy, null=True)
    name = models.CharField(max_length=255)

    source_name = 'OtherDummy'
    source_class = OtherDummy

    @property
    def source(self):
        return self.other_dummy

    @source.setter
    def source(self, value):
        self.other_dummy = value


# Simplest possible revision that has a source class defined.
class SimpleSource(models.Model):
    class Meta:
        app_label = 'gcd'


class SimpleSourceRevision(Revision):
    class Meta:
        app_label = 'oi'

    source_class = SimpleSource


# The simplest possible revision, without a source hooked up.
# Used to test the non-overridden abstract base methods.
class SimplestRevision(Revision):
    class Meta:
        app_label = 'oi'
