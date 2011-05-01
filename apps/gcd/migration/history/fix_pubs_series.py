import sys
import datetime

from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import User

from apps.gcd.models import Country, Language, Publisher, Series
from apps.oi.models import Changeset, PublisherRevision, SeriesRevision, CTYPES
from apps.oi import states

from apps.gcd.migration import ANON_USER
from apps.gcd.migration.history import \
    COMMENT_TEXT, COMMENT_TEXT_FOR_ADD, MigratoryChangeset
from apps.gcd.migration.history.publisher import MigratoryPublisherRevision
from apps.gcd.migration.history.series import MigratorySeriesRevision

class VieuxBoisPublisher(models.Model):
    class Meta:
        db_table = 'old_publisher'
        app_label = 'gcd'

    name = models.CharField(max_length=255, db_index=True)
    # country_id = models.IntegerField()
    country = models.ForeignKey(Country)
    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    notes = models.TextField()
    url = models.URLField()
    is_master = models.BooleanField()
    # parent_id = models.IntegerField()
    parent = models.ForeignKey(Publisher)

    # Fields related to change management.
    created = models.DateField(auto_now_add=True)
    modified = models.DateField(auto_now=True)

    def __unicode__(self):
        return self.name

class VieuxBoisSeries(models.Model):
    class Meta:
        db_table = 'old_series'
        app_label = 'gcd'
    
    name = models.CharField(max_length=255, db_index=True)
    format = models.CharField(max_length=255)

    year_began = models.IntegerField(db_index=True)
    year_ended = models.IntegerField(null=True)
    publication_dates = models.CharField(max_length=255)

    publisher = models.ForeignKey(Publisher)
    imprint = models.ForeignKey(Publisher, null=True,
                                related_name='vieux_bois_imprint_series')
    country = models.ForeignKey(Country)
    language = models.ForeignKey(Language)

    # publisher_id = models.IntegerField()
    # imprint_id = models.IntegerField()
    # country_id = models.IntegerField()
    # language_id = models.IntegerField()

    tracking_notes = models.TextField()
    notes = models.TextField()
    publication_notes = models.TextField()

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s (%s series)' % (self.name, self.year_began)

def fix_pubs():
    old_pubs = Publisher.objects.filter(
      created__lte=settings.NEW_SITE_CREATION_DATE,
      parent__isnull=True, is_master=True)

    no_prior_revs = old_pubs.exclude(
      revisions__created__lte=settings.NEW_SITE_CREATION_DATE)

    print "%d publishers to fix..." % no_prior_revs.count()
    for pub in no_prior_revs:
        print "Fixing publisher %s" % pub
        old = VieuxBoisPublisher.objects.get(pk=pub.pk)

        # Create changeset
        changeset = Changeset(indexer=ANON_USER, approver=ANON_USER,
                              state=states.APPROVED,
                              change_type=CTYPES['publisher'],
                              migrated=True, date_inferred=True)
        changeset.save()

        # Circumvent automatic field behavior.
        # all dates and times guaranteed to be valid
        mc = MigratoryChangeset.objects.get(id=changeset.id)
        mc.created = old.created
        mc.modified = old.modified
        mc.save()
        changeset = Changeset.objects.get(id=changeset.id)

        comment_text = COMMENT_TEXT + COMMENT_TEXT_FOR_ADD
        changeset.comments.create(commenter=ANON_USER,
                                  text=comment_text,
                                  old_state=states.APPROVED,
                                  new_state=states.APPROVED)
        comment = changeset.comments.all()[0]
        comment.created = changeset.created
        comment.save()

        revision = PublisherRevision(changeset=changeset,
                                     publisher=pub,
                                     country=old.country,
                                     is_master=old.is_master,
                                     name=old.name,
                                     year_began=old.year_began,
                                     year_ended=old.year_ended,
                                     notes=old.notes,
                                     url=old.url,
                                     date_inferred=True)
        revision.save()

        # Circumvent automatic field behavior.
        mr = MigratoryPublisherRevision.objects.get(id=revision.id)
        mr.created = changeset.created
        mr.modified = changeset.created
        mr.save()

def fix_series():
    old_series = Series.objects.filter(
      created__lte=settings.NEW_SITE_CREATION_DATE)

    no_prior_revs = old_series.exclude(
      revisions__created__lte=settings.NEW_SITE_CREATION_DATE)

    print "%d series to fix..." % no_prior_revs.count()
    for series in no_prior_revs:
        print "Fixing series %s" % series
        old = VieuxBoisSeries.objects.get(pk=series.pk)

        # Create changeset
        changeset = Changeset(indexer=ANON_USER, approver=ANON_USER,
                              state=states.APPROVED,
                              change_type=CTYPES['series'],
                              migrated=True, date_inferred=True)
        changeset.save()

        # Circumvent automatic field behavior.
        # all dates and times guaranteed to be valid
        mc = MigratoryChangeset.objects.get(id=changeset.id)
        mc.created = old.created
        mc.modified = old.modified
        mc.save()
        changeset = Changeset.objects.get(id=changeset.id)

        comment_text = COMMENT_TEXT + COMMENT_TEXT_FOR_ADD
        changeset.comments.create(commenter=ANON_USER,
                                  text=comment_text,
                                  old_state=states.APPROVED,
                                  new_state=states.APPROVED)
        comment = changeset.comments.all()[0]
        comment.created = changeset.created
        comment.save()

        revision = SeriesRevision(changeset=changeset,
                                  series=series,
                                  country=old.country,
                                  language=old.language,
                                  publisher=old.publisher,
                                  name=old.name,
                                  imprint=old.imprint,
                                  format=old.format,
                                  year_began=old.year_began,
                                  year_ended=old.year_ended,
                                  publication_notes=old.publication_notes,
                                  tracking_notes=old.tracking_notes,
                                  notes=old.notes,
                                  date_inferred=True)
        revision.save()

        # Circumvent automatic field behavior.
        mr = MigratorySeriesRevision.objects.get(id=revision.id)
        mr.created = changeset.created
        mr.modified = changeset.created
        mr.save()

@transaction.commit_on_success
def main():
    fix_pubs()
    print '\n'
    fix_series()

if __name__ == '__main__':
    main()
