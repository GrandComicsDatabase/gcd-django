import sys
import logging
import datetime
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from apps.gcd.migration.history import MigratoryTable, LogRecord

class MigratoryPublisherRevision(MigratoryTable):
    class Meta(MigratoryTable.Meta):
        db_table = 'oi_publisher_revision'
        managed = False

class LogPublisher(LogRecord):
    class Meta(LogRecord.Meta):
        db_table = 'log_publisher'
        app_label = 'gcd'

    PubName = models.CharField(max_length=255)
    Notes = models.TextField(blank=True)
    YearBegan = models.IntegerField(null=True)
    YearEnded = models.IntegerField(null=True)
    CountryID = models.CharField(max_length=4)
    Country = models.ForeignKey('gcd.Country', db_column='CountryID')
    PublisherID = models.IntegerField()
    DisplayPublisher = models.ForeignKey('gcd.Publisher', db_column='PublisherID')
    Web = models.CharField(max_length=255, blank=True)

    ctype = CTYPES['publisher']
    ctype_add = ctype
    migratory_class = MigratoryPublisherRevision

    @classmethod
    def original_table(klass):
        return 'LogPublishers'

    @classmethod
    def display_table(klass):
        return 'gcd_publisher'

    @classmethod
    def source_id(klass):
        return 'PublisherID'

    @classmethod
    def extra_delete_where(klass):
        return 'OR d.is_master = 0'

    @classmethod
    def group_duplicate_fields(klass):
        return ('pubname collate utf8_bin, notes collate utf8_bin, yearbegan, '
                'yearended, countryid, publisherid, web')

    @classmethod
    def alter_table(klass, anon):
        cursor = connection.cursor()
        cursor.execute("""
ALTER TABLE log_publisher
    DROP COLUMN Connection,
    DROP COLUMN ParentID,
    DROP COLUMN Master,
    CHANGE COLUMN ModifiedTime ModTime time default NULL,
    %s,
    ADD INDEX (PublisherID);
""" % klass._common_alter_clauses())

        logging.info("Table altered, inserting data.")
        cursor.execute("""
INSERT INTO log_publisher
    (PubName, Notes, YearBegan, YearEnded, CountryID, Web, UserID, PublisherID)
  SELECT
    name, notes, year_began, year_ended, country_id, url, %d, id
  FROM old_publisher;
""" % anon.id)

    @classmethod
    def fix_values(klass, anon, unknown_country, undetermined_language):
        cursor = connection.cursor()
        # Set 'uk' country to 'gb'
        cursor.execute("""
UPDATE log_publisher SET CountryID = 75 WHERE CountryID = 223
""")
        # Set unknown countries to the special unknown value, convert codes to ids.
        cursor.execute("""
UPDATE log_publisher p LEFT OUTER JOIN gcd_country c ON p.CountryID = c.id
    SET p.CountryID=%d WHERE c.id IS NULL;
""" % unknown_country.id)
        cursor.close()

        klass.objects.filter(Notes__isnull=True).update(Notes='')
        klass.objects.filter(Web__isnull=True).update(Web='')

    @classmethod
    def add_special_times(klass):
        # update a few times manually where some publishers had a mix of records
        # with dates and times and some without.
        klass.objects.filter(ID__in=(1865, 1877, 1359))\
                     .update(ModTime=datetime.time(23, 0, 0))
        klass.objects.filter(
          ID__in=(1870, 1872, 1875, 1876, 161, 1590, 1315))\
                     .update(ModTime=datetime.time(0, 0, 0))
        klass.objects.filter(ID__in=(1360, 1164))\
                     .update(ModTime=datetime.time(0, 0, 1))
        klass.objects.filter(ID=1361)\
                     .update(ModTime=datetime.time(0, 0, 1))

    @classmethod
    def get_related(klass):
        return ('Country', 'DisplayPublisher', 'User__user')

    def revision_exists(self):
        if PublisherRevision.objects.filter(created=self.dt, publisher=self.DisplayPublisher):
            return True
        else:
            return False

    def convert(self, changeset):
        # create publisher revision, is_master always true since not
        # migrating imprints
        revision = PublisherRevision(changeset=changeset,
                                     publisher=self.DisplayPublisher,
                                     country=self.Country,
                                     is_master=1,
                                     name=self.PubName,
                                     year_began=self.YearBegan,
                                     year_ended=self.YearEnded,
                                     notes=self.Notes,
                                     url=self.Web,
                                     date_inferred=changeset.date_inferred)
        revision.save()
        return revision

