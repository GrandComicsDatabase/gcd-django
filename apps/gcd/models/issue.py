from django.db import models

from series import Series

class Issue(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['series', 'sort_code']

    # Core issue attributes.
    # Note that volume is not consistently used at this time, and
    # is usually included in 'number' when it is of critical importance.
    volume = models.IntegerField(max_length=255, db_index=True)
    number = models.CharField(max_length=25, null=True, db_index=True)
    display_volume_with_number = models.BooleanField(default=False)
    publication_date = models.CharField(max_length=255, null=True)
    price = models.CharField(max_length=255, null=True)
    story_count = models.IntegerField(null=True)
    key_date = models.CharField(max_length=10, null=True)
    sort_code = models.IntegerField(db_index=True)

    # Fields related to indexing activities.
    # Only "reserved" is in active use, the others are legacy fields
    # used only by migration scripts.
    reserved = models.BooleanField(default=0, db_index=True)
    index_status = models.IntegerField(null=True)
    reserve_status = models.IntegerField(db_index=True)
    reserve_check = models.NullBooleanField(db_index=True)

    series = models.ForeignKey(Series)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True, db_index=True)
    
    def display_number(self):
        if self.display_volume_with_number:
            return u'v%s#%s' % (self.volume, self.number)
        return self.number

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

    def reserver(self):
        """
        Return the likely current reservation holder.  While it is common
        for an issue to have multiple reservation records for the same issue
        in the same status, at no point in the current (at this time) data set
        does an issue have more than one unapproved reservation record with
        differen indexers in each.  So taking the first 
        """
        if self.index_status in (1, 2):
            reservers = self.reservation_set.filter(status=self.index_status)
            if reservers.count() > 0:
                return reservers[0].indexer
        return None

    def get_absolute_url(self):
        return "/issue/%i/" % self.id

    def __unicode__(self):
        return u'%s #%s' % (self.series, self.number)

