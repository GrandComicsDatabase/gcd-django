from django.db import models
from django.contrib.auth.models import User
from apps.gcd.models.series import Series
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from datetime import time

class LogSeries(models.Model):
    class Meta:
        db_table = 'log_series'
        app_label = 'gcd'

    ID = models.BigIntegerField(primary_key=True)
    Bk_Name = models.CharField(max_length=255)
    CounCode = models.CharField(max_length=4)
    Format = models.CharField(max_length=255)
    LangCode = models.CharField(max_length=4)
    Modified = models.DateField()
    ModTime = models.TimeField()
    Notes = models.TextField(blank=True)
    PubID = models.BigIntegerField()
    Pub_Note = models.TextField(blank=True)
    SeriesID = models.BigIntegerField()
    Tracking = models.TextField(blank=True)
    Yr_Began = models.IntegerField()
    Yr_Ended = models.IntegerField(null=True)
    UserID = models.IntegerField()
    ImprintID = models.BigIntegerField(null=True)


def create_series_revision(old_change, anon):
    # create changeset
    indexer = Indexer.objects.get(id=old_change.UserID)
    changeset = Changeset(indexer=indexer.user, approver=anon,
                          state=states.APPROVED, change_type=CTYPES['series'])
    changeset.save()

    # all dates and times guaranteed to be valid
    changeset.created = datetime.combine(old_change.Modified, old_change.ModTime)
    changeset.save()

    changeset.comments.create(commenter=indexer.user,
                              text='This change history was migrated from the old site.',
                              old_state=states.APPROVED, new_state=states.APPROVED)
    comment = changeset.comments.all()[0]
    comment.created = changeset.created
    comment.save()

    series = Series.objects.get(id=old_change.SeriesID)
    country = Country.objects.get(id=old_change.CounCode)
    language = Language.objects.get(id=old_change.LangCode)
    publisher = Publisher.objects.get(id=old_change.PubID)
    if old_change.ImprintID is not None:
        imprint = Publisher.objects.get(id=old_change.ImprintID)
    else:
        imprint = old_change.ImprintID
    revision = SeriesRevision(changeset=changeset, series=series,
                              name=old_change.Bk_Name,
                              format=old_change.Format,
                              year_began=old_change.Yr_Began,
                              year_ended=old_change.Yr_Ended,
                              publication_notes=old_change.Pub_Note,
                              tracking_notes=old_change.Tracking,
                              notes=old_change.Notes, country=country,
                              language=language, publisher=publisher,
                              imprint=imprint)
    revision.save()
    revision.created = changeset.created
    revision.save()

def add_times(no_time_series):
    series_id = no_time_series[0].SeriesID
    series_date = no_time_series[0].Modified
    seconds = 0

    # reset the seconds between series as well as between dates inside that series
    # result is like the following data (only the first had both, others only dates)
    # 2002-10-13 - 04:30:42
    # 2006-05-11 - 00:00:00
    # 2006-05-11 - 00:00:01
    # 2006-05-11 - 00:00:02
    # 2007-01-05 - 00:00:00
    # 2008-03-11 - 00:00:00
    # 2008-03-11 - 00:00:01
    for change in no_time_series:
        if series_id != change.SeriesID:
            seconds = 0
            series_id = change.SeriesID
            series_date = change.Modified
        elif series_date != change.Modified:
            seconds = 0
            series_date = change.Modified
        new_time = time(0, 0, seconds)

        if change.ModTime is None:
            change.ModTime = new_time
            change.save()
            seconds += 1

def import_series_history():
    series_history = LogSeries.objects.all()

    # some series have entries that have dates and times as well as ones with only dates.
    # luckily none of them have a date/time and then a later one with the same date but no time.
    # if that were the case we couldn't just use 00:00:00 because it'd sort before the existing one.
    # some commented out parts that were necessary to figure this out (and might be 
    # necessary for issues/stories).

    # mod_time_null = series_history.filter(ModTime__isnull=True).values_list('SeriesID', flat=True)
    # mod_time_not_null = series_history.filter(ModTime__isnull=False).values_list('SeriesID', flat=True)

    # list of series whose log entries are a mix of null and non-null times
    # use list() to force subquery execution or script runs *really* slowly
    # see Performance Considerations at http://docs.djangoproject.com/en/dev/ref/models/querysets/#in

    # mixed_series = series_history.filter(SeriesID__in=list(mod_time_not_null)) \
    #  .filter(SeriesID__in=list(mod_time_null)).order_by('SeriesID', 'ID')

    add_times(series_history.filter(ModTime__isnull=True).order_by('SeriesID', 'ID'))

    anon = User.objects.get(id=381)
    for change in series_history:
        create_series_revision(change, anon)

import_series_history()