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
                              null = True)
    # Note that in stories, publication_date is limited to 50 chars.
    publication_date = models.CharField(max_length = 255,
                                        db_column = 'Pub_Date',
                                        null = True)
    price = models.CharField(max_length = 25, db_column = 'Price', null = True)
    story_count = models.IntegerField(db_column = 'storycount', null = True)
    key_date = models.CharField(max_length = 10, db_column = 'Key_Date',
                                null = True)

    # Fields related to indexing activities.
    index_status = models.IntegerField(db_column = 'IndexStatus', null = True)
    reserve_status = models.IntegerField(db_column = 'ReserveStatus',
                                         null = True)

    # Attributes from series table. First is foreign key, rest are
    # dups and seem to be ignored in the lasso implementation
    series = models.ForeignKey(Series,
                               db_column = 'SeriesID')

    # Fields related to change management.
    created = models.DateField(auto_now_add = True, null = True)
    modified = models.DateField(db_column = 'Modified',
                                auto_now = True, null = True)
    modification_time = models.TimeField(db_column = 'ModTime',
                                         auto_now = True, null = True)
    
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
        return "/issue/%i/" % self.id

    def __unicode__(self):
        return unicode(self.series.name) + " #" + self.number # + " (" + \
               # self.publication_date + ") [" + self.key_date + "]"

