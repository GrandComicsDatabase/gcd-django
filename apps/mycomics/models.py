# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.db import models
from django.utils.safestring import mark_safe
from django.core import urlresolvers

from model_utils import Choices

from apps.gcd.models import Issue, Series
from apps.stddata.models import Currency, Date, Language
from taggit.managers import TaggableManager

# Create your models here.

class CollectorManager(models.Manager):
    def create_collector(self, user, grade_system=None, default_language=None):
        """Creates and saves Collector instances."""
        if not user:
            raise ValueError('User must be given.')
        collector = self.model(user=user)
        if grade_system is None:
            collector.grade_system = ConditionGradeScale.objects.get(pk=1)
        else:
            collector.grade_system = grade_system
        if default_language is None:
            collector.default_language = Language.objects.get(code='en')
        else:
            collector.default_language = default_language
        collector.save()
        default_have_collection = Collection(collector=collector,
                                             name='Default have collection',
                                             condition_used=True,
                                             acquisition_date_used=True,
                                             location_used=True,
                                             purchase_location_used=True,
                                             was_read_used=True,
                                             for_sale_used=True,
                                             signed_used=True,
                                             price_paid_used=True)
        default_have_collection.save()
        default_want_collection = Collection(collector=collector,
                                             name='Default want collection',
                                             market_value_used=True)
        default_want_collection.save()
        collector.default_have_collection = default_have_collection
        collector.default_want_collection = default_want_collection
        collector.save()


class Collector(models.Model):
    """Class representing a collector side of the user."""
    user = models.OneToOneField(User)

    grade_system = models.ForeignKey('ConditionGradeScale', related_name='+')

    #defaults
    default_have_collection = models.ForeignKey('Collection', related_name='+',
                                                null=True)
    default_want_collection = models.ForeignKey('Collection', related_name='+',
                                                null=True)
    default_language = models.ForeignKey(Language, related_name='+')

    default_currency = models.ForeignKey(Currency, related_name='+',
                                           null=True, blank=True)

    objects = CollectorManager()

    def ordered_collections(self):
        """
        Default collections come first, the rest in alphabetical order.
        """
        collections_list = [self.default_have_collection,
                            self.default_want_collection]
        other = self.collections.exclude(id=self.default_have_collection.id)\
                                .exclude(id=self.default_want_collection.id)\
                                .order_by('name')
        collections_list.extend(list(other))
        return collections_list


class Collection(models.Model):
    """Class for keeping info about particular collections together with
    configuration of item fields used in each collection."""
    collector = models.ForeignKey(Collector, related_name='collections')

    name = models.CharField(blank=False, max_length=255, db_index=True)
    description = models.TextField(blank=True)
    keywords = TaggableManager(blank=True)

    public = models.BooleanField(default=False,
               verbose_name="collection is public and can be viewed by all")

    #Configuration of fields used - notes and keywords are assumed to be always
    # 'on'.
    condition_used = models.BooleanField(default=False,
                                         verbose_name="show condition")
    acquisition_date_used = models.BooleanField(default=False,
                                   verbose_name="show acquisition date")
    sell_date_used = models.BooleanField(default=False,
                                         verbose_name="show sell data")
    location_used = models.BooleanField(default=False,
                                        verbose_name="show location")
    purchase_location_used = models.BooleanField(default=False,
                                    verbose_name="show purchase location")
    own_used = models.BooleanField(default=False,
                                   verbose_name="show own/want status")
    own_default = models.NullBooleanField(default=None,
                            verbose_name="default ownership status when "
                                         "adding items to this collection")
    was_read_used = models.BooleanField(default=False,
                                        verbose_name="show read status")
    for_sale_used = models.BooleanField(default=False,
                                        verbose_name="show for sale status")
    signed_used = models.BooleanField(default=False,
                                      verbose_name="show signed status")
    price_paid_used = models.BooleanField(default=False,
                                          verbose_name="show price paid")
    market_value_used = models.BooleanField(default=False,
                               verbose_name="show entered market value")
    sell_price_used = models.BooleanField(default=False,
                                          verbose_name="show sell price")
    digital_used = models.BooleanField(default=False,
                                       verbose_name="track digitial versions")
    rating_used = models.BooleanField(default=False,
                                      verbose_name="rate comics")
    def get_absolute_url(self):
        return urlresolvers.reverse('view_collection',
                                    kwargs={'collection_id':self.id})

    def __unicode__(self):
        return str(self.name)


class Subscription(models.Model):
    """Class to record the subscription of a particular series in user's
    collection."""

    class Meta:
        db_table = 'mycomics_subscription'

    collection = models.ForeignKey(Collection, related_name="subscriptions")
    series = models.ForeignKey(Series)
    last_pulled = models.DateTimeField()


class Location(models.Model):
    """Class for keeping information about locations of user's collection's
    items."""
    user = models.ForeignKey(Collector)
    name = models.CharField(blank=True, max_length=255)
    description = models.TextField(blank=True)

    def __unicode__(self):
        return str(self.name)


class PurchaseLocation(models.Model):
    """Class for keeping information about locations where users purchased
    theirs collection's items."""
    class Meta:
        db_table='mycomics_purchase_location'
    user = models.ForeignKey(Collector)
    name = models.CharField(blank=True, max_length=255)
    description = models.TextField(blank=True)

    def __unicode__(self):
        return str(self.name)


class CollectionItem(models.Model):
    """Class for keeping record of particular item in user's collection."""

    class Meta:
        db_table = 'mycomics_collection_item'
        ordering = ['issue__series__sort_name', 'issue__series__year_began',
                    'issue__sort_code', 'id']

    RATINGS = Choices(
        (1, 'poor', '1 - Poor'),
        (2, 'fair', '2 - Fair'),
        (3, 'good', '3 - Good'),
        (4, 'very_good ', '4 - Very Good'),
        (5, 'excellent', '5 - Excellent'),
    )

    collections = models.ManyToManyField(Collection, related_name="items",
                                db_table="mycomics_collection_item_collections")
    issue = models.ForeignKey(Issue)

    location = models.ForeignKey(Location, null=True, blank=True,
                                 related_name="items",
                                 on_delete=models.SET_NULL)
    purchase_location = models.ForeignKey(PurchaseLocation, null=True,
                                          blank=True, related_name="items",
                                          on_delete=models.SET_NULL)

    notes = models.TextField(blank=True)
    keywords = TaggableManager(blank=True)

    grade = models.ForeignKey('ConditionGrade', related_name='+', null=True,
                              blank=True)

    acquisition_date = models.ForeignKey(Date, related_name='+', null=True,
                                         blank=True)
    sell_date = models.ForeignKey(Date, related_name='+', null=True, blank=True)

    own = models.NullBooleanField(default=None, verbose_name="ownership")
    was_read = models.NullBooleanField(default=None)
    for_sale = models.BooleanField(default=False)
    signed = models.BooleanField(default=False)

    #price fields
    price_paid = models.DecimalField(max_digits=10, decimal_places=2,
                                     blank=True, null=True)
    price_paid_currency = models.ForeignKey(Currency, related_name='+',
                                            null=True, blank=True)
    market_value = models.DecimalField(max_digits=10, decimal_places=2,
                                       blank=True, null=True)
    market_value_currency = models.ForeignKey(Currency, related_name='+',
                                              null=True, blank=True)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2,
                                     blank=True, null=True)
    sell_price_currency = models.ForeignKey(Currency, related_name='+',
                                            null=True, blank=True)
    rating = models.IntegerField(choices=RATINGS, blank=True, null=True)
    is_digital = models.BooleanField(default=False)

    def show_rating(self):
        if self.rating:
            return CollectionItem.RATINGS[self.rating]
        else:
            return '-'

    def get_absolute_url(self, collection):
        return urlresolvers.reverse('view_item', kwargs={'item_id':self.id,
                                    'collection_id':collection.id})

class ConditionGradeScale(models.Model):
    """Class representing condition grade scale for use by collectors."""
    class Meta:
        db_table='mycomics_condition_grade_scale'

    name=models.CharField(blank=False,max_length=255)
    description=models.CharField(max_length=2000, blank=True)

    def __unicode__(self):
        return str(self.name)


class ConditionGrade(models.Model):
    """Class representing single grade in a condition grade scale."""
    class Meta:
        db_table='mycomics_condition_grade'

    scale=models.ForeignKey(ConditionGradeScale, related_name='grades',
                            null=False)
    code=models.CharField(blank=False, max_length=20)
    name=models.CharField(blank=False, max_length=255)
    value=models.FloatField(blank=False)

    def __cmp__(self, other):
        return self.value.__cmp__(other.value)

    def __unicode__(self):
        return "%s - %s" % (self.code, self.name)

