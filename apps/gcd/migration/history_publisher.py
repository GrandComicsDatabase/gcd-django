from django.db import models
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from datetime import time

class LogPublisher(models.Model):
    class Meta:
        db_table = 'log_publisher'
        app_label = 'gcd'

    ID = models.BigIntegerField(primary_key=True)
    PubName = models.CharField(max_length=255)
    Notes = models.TextField(blank=True)
    YearBegan = models.IntegerField(null=True)
    YearEnded = models.IntegerField(null=True)
    CountryID = models.CharField(max_length=4)
    Modified = models.DateField()
    ModifiedTime = models.TimeField()
    UserID = models.IntegerField()
    PublisherID = models.IntegerField()
    Web = models.CharField(max_length=255, blank=True)


def create_publisher_revision(old_change, anon):
    # create changeset
    indexer = Indexer.objects.get(id=old_change.UserID)
    changeset = Changeset(indexer=indexer.user, approver=anon,
                          state=states.APPROVED, change_type=CTYPES['publisher'])
    changeset.save()

    # all dates and times guaranteed to be valid
    changeset.created = datetime.combine(old_change.Modified, old_change.ModifiedTime)
    changeset.save()

    changeset.comments.create(commenter=indexer.user,
                              text='This change history was migrated from the old site.',
                              old_state=states.APPROVED, new_state=states.APPROVED)
    comment = changeset.comments.all()[0]
    comment.created = changeset.created
    comment.save()

    # create publisher revision, is_master always true since not
    # migrating imprints
    publisher = Publisher.objects.get(id=old_change.PublisherID)
    country = Country.objects.get(id=old_change.CountryID)
    revision = PublisherRevision(changeset=changeset, publisher=publisher,
                                 country=country, is_master=1,
                                 name=old_change.PubName,
                                 year_began=old_change.YearBegan,
                                 year_ended=old_change.YearEnded,
                                 notes=old_change.Notes, url=old_change.Web)
    revision.save()
    revision.created = changeset.created
    revision.save()

def add_times(pub_with_no_times):
    # fill in all the null modifiedtimes, making sure that if there are
    # multiple records for a publisher the time for the first is
    # 00:00:00, the second is 00:00:01, etc.
    pub_with_no_times = pub_with_no_times.order_by('PublisherID', 'ID')
    pub_id = pub_with_no_times[0].PublisherID
    seconds = 0
    for change in pub_with_no_times:
        if pub_id != change.PublisherID:
            seconds = 0
            pub_id = change.PublisherID
        new_time = time(0, 0, seconds)
        change.ModifiedTime = new_time
        change.save()
        seconds += 1

def import_pub_history():
    anon = User.objects.get(id=381)
    pub_history = LogPublisher.objects.all()
    
    add_times(pub_history.filter(ModifiedTime__isnull=True))

    for change in pub_history:
        create_publisher_revision(change, anon)

import_pub_history()