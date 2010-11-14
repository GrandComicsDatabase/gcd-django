import sys
import logging
import datetime
from django.db import models, transaction, connection
from django.contrib.auth.models import User
from apps.gcd.models.publisher import Publisher
from apps.gcd.models.indexer import Indexer
from apps.oi.models import *
from apps.gcd.migration.history import MigratoryTable, LogRecord

class MigratorySeriesRevision(MigratoryTable):
    class Meta(MigratoryTable.Meta):
        db_table = 'oi_series_revision'
        managed = False

class LogSeries(LogRecord):
    class Meta(LogRecord.Meta):
        db_table = 'log_series'
        app_label = 'gcd'

    Bk_Name = models.CharField(max_length=255)
    CounCode = models.CharField(max_length=4)
    Country = models.ForeignKey('gcd.Country')
    Format = models.CharField(max_length=255)
    LangCode = models.CharField(max_length=4)
    Language = models.ForeignKey('gcd.Language')
    Notes = models.TextField(blank=True)
    PubID = models.BigIntegerField()
    DisplayPublisher = models.ForeignKey('gcd.Publisher', db_column='PubID')
    Pub_Note = models.TextField(blank=True)
    SeriesID = models.BigIntegerField()
    DisplaySeries = models.ForeignKey('gcd.Series', db_column='SeriesID')
    Tracking = models.TextField(blank=True)
    Yr_Began = models.IntegerField()
    Yr_Ended = models.IntegerField(null=True)
    ImprintID = models.BigIntegerField(null=True)
    Imprint = models.ForeignKey('gcd.Publisher', db_column='ImprintID', null=True,
                                                 related_name='LogSeriesImprints')

    ctype = CTYPES['series']
    ctype_add = ctype
    migratory_class = MigratorySeriesRevision

    @classmethod
    def original_table(klass):
        return 'LogSeries'

    @classmethod
    def display_table(klass):
        return 'gcd_series'

    @classmethod
    def source_id(klass):
        return 'SeriesID'

    @classmethod
    def group_duplicate_fields(klass):
        return ('Bk_Name, CounCode, Format, LangCode, Notes, PubID, Pub_Note, '
                'SeriesID, Tracking, Yr_Began, Yr_Ended, ImprintID')

    @classmethod
    def alter_table(klass, anon):
        cursor = connection.cursor()
        cursor.execute("""
ALTER TABLE log_series
    ADD COLUMN country_id int(11) default NULL,
    ADD COLUMN language_id int(11) default NULL,
    DROP COLUMN Frst_Iss,
    DROP COLUMN Last_Iss,
    DROP COLUMN Included,
    DROP COLUMN PubDates,
    %s,
    ADD INDEX (SeriesID);
""" % klass._common_alter_clauses())

        logging.info("Table altered, inserting data.")
        cursor.execute("""
INSERT INTO log_series
        (Bk_Name, PubID, CounCode, LangCode, Format, Tracking, Pub_Note, Notes,
         Yr_Began, Yr_Ended, ImprintID, UserID, SeriesID)
    SELECT
        s.name, s.publisher_id, c.code, l.code, s.format, s.tracking_notes,
        s.publication_notes, s.notes, s.year_began, s.year_ended, s.imprint_id, %d, s.id
    FROM migrated.gcd_series s
        INNER JOIN migrated.gcd_country c ON s.country_id = c.id
        INNER JOIN migrated.gcd_language l on s.language_id = l.id;
""" % anon.id)

    @classmethod
    def fix_values(klass, anon, unknown_country, undetermined_language):
        cursor = connection.cursor()

        # Set unknown countries to the special unknown value, convert codes to ids.
        cursor.execute("""
UPDATE log_series s LEFT OUTER JOIN gcd_country c ON s.CounCode = c.code
    SET s.country_id=IF(c.id IS NULL, %d, c.id);
""" % unknown_country.id)

        # Fix a bunch of languages.  Copy-paste from prototype migration script
        # which is why it's a raw SQL execute.  No other reason to avoid ORM here.
        cursor.execute("""
-- Fix language code for Dutch.
UPDATE log_series SET LangCode='nl'
    WHERE CounCode = 'nl' AND LangCode IN ('du', 'dy');

-- Fix language code for Danish.
UPDATE log_series SET LangCode='da'
    WHERE CounCode = 'dk' AND LangCode = 'dk';

-- Fix language code for Swedish.
UPDATE log_series SET LangCode='sv'
    WHERE CounCode = 'se' AND LangCode = 'ev';

-- Fix language code for English.
UPDATE log_series SET LangCode='en'
    WHERE CounCode IN ('us', 'uk', 'jp')
         AND LangCode IN ('us', 'en,', 'en;', 'ed', 'em', 'ea');

-- Fix language code for Spanish.
UPDATE log_series SET LangCode='es'
    WHERE CounCode IN ('us', 'mx') AND LangCode IN ('sp', 'mx');

-- FIX language code for Portuguese.
UPDATE log_series SET LangCode='pt'
    WHERE CounCode = 'us' AND LangCode = 'po';

-- Fix language code for Greek.
UPDATE log_series SET LangCode='el'
    WHERE CounCode = 'gr' AND LangCode IN ('gr', 'gk');

-- Fix language code for Italian.
UPDATE log_series SET LangCode='it'
    WHERE CounCode = 'it' AND LangCode = 'ir';

-- Fix language code for Japanese.
UPDATE log_series SET LangCode='ja'
    WHERE CounCode = 'jp' AND LangCode = 'jp';
""")
        cursor.close()
        cursor = connection.cursor()

        # Set unknown languages to the special language for "undetermined".
        # Convert codes to IDs.
        cursor.execute("""
UPDATE log_series s LEFT OUTER JOIN gcd_language l ON s.LangCode = l.code
    SET s.language_id=IF(l.id IS NULL, %d, l.id);
""" % undetermined_language.id)
        cursor.close()
        cursor = connection.cursor()

        # Set unknown or null publisher to the special unknown publisher object.
        unknown_publisher = Publisher.objects.get(name='unknown')
        cursor.execute("""
UPDATE log_series s LEFT OUTER JOIN gcd_publisher p ON s.PubID = p.id
    SET s.PubID=%d WHERE p.id IS NULL;
""" % unknown_publisher.id)
        cursor.close()
        cursor = connection.cursor()

        # Set unknown imprints to null.
        cursor.execute("""
UPDATE log_series s LEFT OUTER JOIN gcd_publisher i ON s.ImprintID = i.id
    SET s.ImprintID=NULL WHERE i.id IS NULL;
""")
        cursor.close()

        klass.objects.filter(Bk_Name__isnull=True).update(Bk_Name='')
        klass.objects.filter(Format__isnull=True).update(Format='')
        klass.objects.filter(Notes__isnull=True).update(Notes='')
        klass.objects.filter(Pub_Note__isnull=True).update(Pub_Note='')
        klass.objects.filter(Tracking__isnull=True).update(Tracking='')
        klass.objects.filter(Yr_Began__isnull=True).update(Yr_Began=0)

    @classmethod
    def get_related(klass):
        return ('Country', 'Language', 'DisplayPublisher', 'Imprint',
                'DisplaySeries', 'User__user')


    def convert(self, changeset):
        revision = SeriesRevision(changeset=changeset,
                                  series=self.DisplaySeries,
                                  country=self.Country,
                                  language=self.Language,
                                  publisher=self.DisplayPublisher,
                                  imprint=self.Imprint,
                                  name=self.Bk_Name,
                                  format=self.Format,
                                  year_began=self.Yr_Began,
                                  year_ended=self.Yr_Ended,
                                  publication_notes=self.Pub_Note,
                                  tracking_notes=self.Tracking,
                                  notes=self.Notes)
        revision.save()
        return revision

