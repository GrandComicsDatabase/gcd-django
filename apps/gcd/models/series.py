from django.db import models

from country import Country
from language import Language
from publisher import Publisher

class Series(models.Model):

    class Meta:
        db_table = 'series'
        app_label = 'gcd'
    
    class Admin:
        list_display = ('name', 'year_began', 'publisher')

    id = models.AutoField(primary_key = True, db_column = 'ID')

    # Core series fields.
    name = models.CharField(max_length = 255, db_column = 'Bk_Name',
                            null = True)
    format = models.CharField(max_length = 255, db_column = 'Format',
                              null = True)
    notes = models.TextField(db_column = 'Notes', null = True)
    year_began = models.IntegerField(db_column = 'Yr_Began', null = True)
    year_ended = models.IntegerField(db_column = 'Yr_Ended', null = True)
    publication_dates = models.CharField(max_length = 255,
                                         db_column = 'PubDates', null = True)
    publication_notes = models.TextField(db_column = 'Pub_Note', null = True)
    themes = models.TextField(db_column = 'Themes', null = True)
    issue_count = models.IntegerField(db_column = 'Issuecount', null = True)

    # Fields for tracking relationships between series.
    # Crossref fields don't appear to really be used- nearly all null.
    tracking_notes = models.TextField(db_column = 'Tracking', null = True)
    crossref = models.IntegerField(db_column = 'Crossref', null = True)
    crossref_id = models.IntegerField(db_column = 'CrossrefID', null = True)

    # Fields related to cover image galleries.
    gallery_present = models.CharField(max_length = 3, db_column = 'HasGallery',
                                null = True)
    gallery_includes = models.CharField(max_length = 255,
                                        db_column = 'Included',
                                        null = True)
    
    # Fields related to indexing activities.
    indexers = models.TextField(db_column = 'Indexers', null = True)
    open_reserve = models.IntegerField(db_column = 'OpenReserve', null = True)

    # Issue tracking info that should probably be read from issues table.
    # Note that in the issues table, issues can be 25 characters.
    first_issue = models.CharField(max_length = 10, db_column = 'Frst_Iss',
                                   null = True)
    last_issue = models.CharField(max_length = 10, db_column = 'Last_Iss',
                                  null = True)

    # Country info- for some reason not a foreign key to Countries table.
    country_code = models.CharField(max_length = 4, db_column = 'CounCode',
                                    null = True)
    # Language info- for some reason not a foreign key to Languages table.
    language_code = models.CharField(max_length = 3, db_column = 'LangCode',
                                     null = True)

    # Fields related to old-style indexing files.  I think.
    file = models.CharField(max_length = 10, db_column = 'File', null = True)
    initial_distribution = models.IntegerField(db_column = 'InitDist',
                                               null = True)
    update_distribution = models.IntegerField(db_column = 'UpdateDist',
                                              null = True)

    # Fields related to the publishers table.
    # publisher_name is redundant, and currently not used(?) by lasso version.
    publisher = models.ForeignKey(Publisher, db_column = 'PubID', null = True)
    publisher_name = models.CharField(max_length = 255, db_column = 'Pub_Name',
                                      null = True)
    imprint_id = models.IntegerField(default = 0)

    # Fields related to change management.
    created = models.DateField(db_column = 'Created',
                               auto_now_add = True, null = True)
    modified = models.DateField(db_column = 'Modified',
                                auto_now = True, null = True)
    modification_time = models.TimeField(db_column = 'ModTime',
                                         auto_now = True, null = True)
    # Not sure about this one.  May have to do with file dists?
    last_change = models.DateField(db_column = 'LstChang', null = True)

    # Apparently the ID from a previous arrangement of the table?
    old_id = models.IntegerField(db_column = 'oldID', null = True)

    # Fields about which I have no idea.
    self_count = models.IntegerField(db_column = 'SelfCount', null = True)

    def scan_count(self):
        return self.cover_set.filter(has_image = '1').count()

    def __unicode__(self):
        return self.name

