from django.db import models

from series import Series

class Issue(models.Model):
    """ issue from gcd database"""

    class Meta:
        db_table = 'issues'
        app_label = 'gcd'
        ordering = ['key_date']

    class Admin:
        pass

    id = models.AutoField(primary_key = True, db_column = 'ID')

    # Core issue attributes.
    # Note that volume is not consistently used at this time, and
    # is usually included in 'issue' when it is of critical importance.
    volume = models.IntegerField(max_length = 255, db_column = 'VolumeNum',
                                 null = True)
    number = models.CharField(max_length = 25, db_column = 'Issue',
                              core = True, null = True)
    # Note that in stories, publication_date is limited to 50 chars.
    publication_date = models.CharField(max_length = 255,
                                        db_column = 'Pub_Date',
                                        null = True)
    price = models.CharField(max_length = 25, db_column = 'Price', null = True)
    story_count = models.IntegerField(db_column = 'storycount', null = True)
    key_date = models.CharField(max_length = 10, db_column = 'Key_Date',
                                null = True)

    # Currently ignored in favor of the same fields on story 0,
    # but unlike other such fields listed below, these should be here
    # as they usually apply to the whole book, not just the cover.
    #UNUSED: Pg_Cnt, Editing, and Notes are unused fields in the current database schema
    #page_count = models.IntegerField(db_column = 'Pg_Cnt', null = True)
    #editor = models.CharField(max_length = 255, db_column = 'Editing',
    #                          null = True)
    #notes = models.TextField(max_length = 255, db_column = 'Notes',
    #                         null = True)

    # Fields related to indexing activities.
    index_status = models.IntegerField(db_column = 'IndexStatus', null = True)
    reserve_status = models.IntegerField(db_column = 'ReserveStatus',
                                         null = True)
    #UNUSED: ReserveCheck is an unused field in the current database schema
    #reserve_check = models.IntegerField(db_column = 'ReserveCheck', null = True)

    # Fields related to cover images
    #UNUSED: CoverCheck and CoverCount are unused fields in the current database schema
    #has_cover = models.IntegerField(db_column = 'CoverCheck', null = True)
    #num_covers = models.IntegerField(db_column = 'CoverCount', null = True)

    # Attributes from series table. First is foreign key, rest are
    # dups and seem to be ignored in the lasso implementation
    series = models.ForeignKey(Series,
                               db_column = 'SeriesID',
                               raw_id_admin = True)
    #UNUSED: Bk_Name and Yr_Began are unused fields in the current database schema
    #series_name = models.CharField(max_length = 255, db_column = 'Bk_Name',
    #                               null = True)
    #year_began = models.IntegerField(db_column = 'Yr_Began', null = True)


    # Attributes from publishers table.  For some reason only the name
    # is entered here, with no traditional foreign key id.
    #UNUSED: Pub_Name is an unused field in the current database schema
    #publisher_name = models.CharField(max_length = 255, db_column = 'Pub_Name',
    #                                  null = True)

    # Fields related to old flat file format.  I think.
    # I think is_updated has to do with this, and not general change tracking.
    # But I'm not sure.
    #UNUSED: InitDist, UpdateDist, and isUpdated are unused fields in the current database schema
    #initial_distribution = models.IntegerField(db_column = 'InitDist',
    #                                           null = True)
    #update_distribution = models.IntegerField(db_column = 'UpdateDist',
    #                                          null = True)
    #is_updated = models.IntegerField(db_column = 'isUpdated', null = True)

    # Fields related to change management.
    created = models.DateField(auto_now_add = True, null = True)
    modified = models.DateField(db_column = 'Modified',
                                auto_now = True, null = True)
    modification_time = models.TimeField(db_column = 'ModTime',
                                         auto_now = True, null = True)
    # Not sure about this one.  May have to do with file dists?
    #UNUSED: LstChang is an unused field in the current database schema
    #last_change = models.DateField(db_column = 'LstChang', null = True)

    # Fields I have no idea what to do with.  Especially SelfCount.
    # I can't even figure out what rel_year stands for.  Release Year?
    #UNUSED: rel_year, SelfCount, and SeriesLink are unused fields in the current database schema
    #rel_year = models.IntegerField(null = True)
    #self_count = models.IntegerField(db_column = 'SelfCount', null = True)
    #series_link = models.IntegerField(db_column = 'SeriesLink', null = True)

    # Attributes borrowed from stories table for cover feature.
    # The lasso implementation appears to ignore these fields and instead
    # use those from feature 0.  Note that page_count and editor
    # technically belong here, but the should actually be on the issue
    # so they are named as such in hopes of getting this fixed eventually.
    #UNUSED: Feature, Char_App, Script, Pencils, Inks, Colors, Letters, Title,
    #UNUSED: Synopsis, Reprints, Genre, Type, Seq_No, and SeriesLink are
    #UNUSED: unused fields in the current database schema
    #cover_feature = models.CharField(max_length = 255, db_column = 'Feature',
    #                                 null = True)
    #cover_characters = models.TextField(db_column = 'Char_App',
    #                                    null = True)
    #cover_script = models.CharField(max_length = 255, db_column = 'Script',
    #                                null = True)
    #cover_pencils = models.CharField(max_length = 255, db_column = 'Pencils',
    #                                 null = True)
    #cover_inks = models.CharField(max_length = 255, db_column = 'Inks',
    #                              null = True)
    #cover_colors = models.CharField(max_length = 255, db_column = 'Colors',
    #                                null = True)
    #cover_letters = models.CharField(max_length = 255, db_column = 'Letters',
    #                                 null = True)
    #cover_title = models.CharField(max_length = 255, db_column = 'Title',
    #                               null = True)
    #cover_synopsis = models.TextField(max_length = 255, db_column = 'Synopsis',
    #                                  null = True)
    #cover_reprints = models.TextField(max_length = 255, db_column = 'Reprints',
    #                                  null = True)
    #cover_genre = models.CharField(max_length = 255, db_column = 'Genre',
    #                               null = True)
    #cover_type = models.CharField(max_length = 255, db_column = 'Type',
    #                              null = True)
    #cover_sequence_number = models.IntegerField(db_column = 'Seq_No',
    #                                            null = True)
    
    def index_status_description(self):
        """Text form of status.  If clauses arranged in order of most
        likely case to least."""
        if (self.index_status == 3):
            return 'approved'
        if (self.index_status == 0):
            return 'no data'
        if (self.index_status == 1):
            return 'reserved'
        if (self.index_status == 2):
            return 'pending'

    def get_absolute_url(self):
        return "/gcd/issue/%i/" % self.id

    def __unicode__(self):
        return str(self.series.name) + " #" + self.number # + " (" + \
               # self.publication_date + ") [" + self.key_date + "]"

