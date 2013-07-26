from django.db import models
from django.core import urlresolvers
from country import Country
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from taggit.managers import TaggableManager

from apps.oi import states
from image import Image

class BasePublisher(models.Model):
    class Meta:
        abstract = True

    # Core publisher fields.
    name = models.CharField(max_length=255, db_index=True)
    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    year_began_uncertain = models.BooleanField(blank=True, db_index=True)
    year_ended_uncertain = models.BooleanField(blank=True, db_index=True)
    notes = models.TextField()
    keywords = TaggableManager()
    url = models.URLField(max_length=255, blank=True, default=u'')

    # Fields related to change management.
    reserved = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    deleted = models.BooleanField(default=False, db_index=True)

    def has_keywords(self):
        return self.keywords.exists()

    def delete(self):
        self.deleted = True
        self.reserved = False
        self.save()

    def __unicode__(self):
        return self.name

class Publisher(BasePublisher):
    class Meta:
        ordering = ['name']
        app_label = 'gcd'

    country = models.ForeignKey(Country)

    # Cached counts.
    imprint_count = models.IntegerField(default=0)
    brand_count = models.IntegerField(default=0, db_index=True)
    indicia_publisher_count = models.IntegerField(default=0, db_index=True)
    series_count = models.IntegerField(default=0)
    issue_count = models.IntegerField(default=0)

    # Deprecated fields about relating publishers/imprints to each other
    # Probably can be removed from model definition
    is_master = models.BooleanField(db_index=True)
    parent = models.ForeignKey('self', null=True,
                               related_name='imprint_set')

    def active_brands(self):
        return self.brand_set.exclude(deleted=True)

    def active_brands_no_pending(self):
        """
        Active brands, not including those with pending deletes.
        Used in some cases where we don't want someone to add to a brand that is
        in the process of being deleted.
        """
        return self.active_brands().exclude(revisions__deleted=True,
          revisions__changeset__state__in=states.ACTIVE)

    def active_indicia_publishers(self):
        return self.indiciapublisher_set.exclude(deleted=True)

    def active_indicia_publishers_no_pending(self):
        """
        Active indicia publishers, not including those with pending deletes.
        Used in some cases where we don't want someone to add to an ind pub that is
        in the process of being deleted.
        """
        return self.active_indicia_publishers().exclude(revisions__deleted=True,
          revisions__changeset__state__in=states.ACTIVE)

    def active_series(self):
        return self.series_set.exclude(deleted=True)

    def deletable(self):
        # TODO: check for issue_count instead of series_count. Check for added
        # issue skeletons. Also delete series and not just brands, ind pubs,
        # and imprints.
        active = { 'changeset__state__in': states.ACTIVE }
        return self.series_count == 0 and \
          self.series_revisions.filter(**active).count() == 0 and \
          self.brand_revisions.filter(**active).count() == 0 and \
          self.indicia_publisher_revisions.filter(**active).count() == 0

    def pending_deletion(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE,
                                     deleted=True).count() == 1

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_publisher',
            kwargs={'publisher_id': self.id } )

    def get_official_url(self):
        """
        TODO: This needs to be retired now that the data has been cleaned up.
        If we want to ensure '' instead of None we should set the db column
        to NOT NULL default ''.
        """
        if self.url is None:
            return ''
        return self.url

    def get_full_name(self):
        return self.name

class IndiciaPublisher(BasePublisher):
    class Meta:
        db_table = 'gcd_indicia_publisher'
        ordering = ['name']
        app_label = 'gcd'

    parent = models.ForeignKey(Publisher)
    is_surrogate = models.BooleanField(db_index=True)
    country = models.ForeignKey(Country)

    issue_count = models.IntegerField(default=0)

    def deletable(self):
        active = self.issue_revisions.filter(changeset__state__in=states.ACTIVE)
        return self.issue_count == 0 and active.count() == 0

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_indicia_publisher',
            kwargs={'indicia_publisher_id': self.id } )

    def __unicode__(self):
        return self.name

class Brand(BasePublisher):
    class Meta:
        ordering = ['name']
        app_label = 'gcd'

    parent = models.ForeignKey(Publisher)

    issue_count = models.IntegerField(default=0)

    image_resources = generic.GenericRelation(Image)

    def _emblem(self):
        img = Image.objects.filter(object_id=self.id, deleted=False,
          content_type = ContentType.objects.get_for_model(self), type__id=3)
        if img:
            return img.get()
        else:
            return None
    emblem = property(_emblem)

    def deletable(self):
        return self.issue_count == 0 and \
          self.issue_revisions.filter(changeset__state__in=states.ACTIVE)\
                              .count() == 0

    def active_issues(self):
        return self.issue_set.exclude(deleted=True)

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'show_brand',
            kwargs={'brand_id': self.id } )

    def full_name(self):
        return unicode(self)

    def __unicode__(self):
        return self.name
