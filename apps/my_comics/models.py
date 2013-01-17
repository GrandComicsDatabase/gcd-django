# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.db import models
from apps.gcd.models import Issue, Language
from apps.stddata.models import Currency, Date
from taggit.managers import TaggableManager

# Create your models here.

class Collector(models.Model):
    """Class representing a collector side of the user."""
    user = models.OneToOneField(User)

    condition_grade_system_code = models.CharField(blank=True, max_length=3)

    #defaults
    default_have_collection = models.ForeignKey('Collection', related_name='+')
    default_want_collection = models.ForeignKey('Collection', related_name='+')
    default_language = models.ForeignKey(Language, related_name='+')

class Collection(models.Model):
    """Class for keeping info about particular collections together with
    configuration of item fields used in each collection."""
    collector = models.ForeignKey(Collector, related_name='collections',
                                  null=False)

    name = models.CharField(blank=False, max_length=255, db_index=True)
    description = models.TextField(blank=True)
    keywords = TaggableManager()

    public = models.BooleanField(default=False)

    #Configuration of fields used - notes and keywords are assumed to be always
    # 'on'.
    condition_used = models.BooleanField(default=False)
    acquisition_date_used = models.BooleanField(default=False)
    sell_date_used = models.BooleanField(default=False)
    location_used = models.BooleanField(default=False)
    purchase_location_used = models.BooleanField(default=False)
    was_read_used = models.BooleanField(default=False)
    for_sale_used = models.BooleanField(default=False)
    signed_used = models.BooleanField(default=False)
    price_paid_used = models.BooleanField(default=False)
    market_value_used = models.BooleanField(default=False)
    sell_price_used = models.BooleanField(default=False)

class Location(models.Model):
    """Class for keeping information about locations of user's collection's
    items."""
    user = models.ForeignKey(Collector)
    name = models.CharField(blank=True, max_length=255)
    description = models.TextField(blank=True)

class PurchaseLocation(models.Model):
    """Class for keeping information about locations where users purchased
    theirs collection's items."""
    user = models.ForeignKey(Collector)
    name = models.CharField(blank=True, max_length=255)
    description = models.TextField(blank=True)

class CollectionItem(models.Model):
    """Class for keeping record of particular item in user's collection."""
    collections = models.ManyToManyField(Collection, related_name="items")
    issue = models.ForeignKey(Issue)

    location = models.ForeignKey(Location)
    purchase_location = models.ForeignKey(PurchaseLocation)

    notes = models.TextField(blank=True)
    keywords = TaggableManager()

    condition_grade_code = models.CharField(blank=True, max_length=10)

    #TODO add removing these dates together with CollectionItem
    acquisition_date = models.ForeignKey(Date, related_name='+')
    sell_date = models.ForeignKey(Date, related_name='+')

    was_read = models.NullBooleanField(default=None)
    for_sale = models.BooleanField(default=False)
    signed = models.BooleanField(default=False)

    #price fields
    price_paid = models.FloatField(blank=True, null=True)
    price_paid_currency = models.ForeignKey(Currency, related_name='+')
    market_value = models.FloatField(blank=True, null=True)
    market_value_currency = models.ForeignKey(Currency, related_name='+')
    sell_price = models.FloatField(blank=True, null=True)
    sell_price_currency = models.ForeignKey(Currency, related_name='+')

class ConditionGrade:
    """Class representing single grade in a condition grade scale."""
    def __init__(self, code, name, value):
        self.code = code
        self.name = name
        self.value = value

    def __cmp__(self, other):
        return self.value.__cmp__(other.value)

class ConditionGradeScale:
    """Class representing condition grade scale for use by collectors."""
    def __init__(self, code, name, grade_map):
        self.code = code
        self.name = name
        self.grade_map = grade_map

    def __getitem__(self, item):
        return self.grade_map[item]

