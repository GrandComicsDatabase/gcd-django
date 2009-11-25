from django.db import models

from publisher import IndiciaPublisher, Brand
from series import Series

class Issue(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['series', 'sort_code']

    # Issue identification
    number = models.CharField(max_length=25, db_index=True)
    volume = models.IntegerField(max_length=255, db_index=True, null=True)
    no_volume = models.BooleanField(default=0)
    display_volume_with_number = models.BooleanField(default=False)

    # Dates and sorting
    publication_date = models.CharField(max_length=255)
    key_date = models.CharField(max_length=10)
    sort_code = models.IntegerField(db_index=True)
    indicia_frequency = models.CharField(max_length=255)

    # Price, page count and format fields
    price = models.CharField(max_length=255)
    page_count = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    page_count_uncertain = models.BooleanField(default=0)
    size = models.CharField(max_length=255)
    paper_stock = models.CharField(max_length=255)
    binding = models.CharField(max_length=255)
    printing_process = models.CharField(max_length=255)

    editing = models.TextField()
    notes = models.TextField()

    # Fields related to indexing activities.
    # Only "reserved" is in active use, the others are legacy fields
    # used only by migration scripts.
    reserved = models.BooleanField(default=0, db_index=True)
    index_status = models.IntegerField(null=True)
    reserve_status = models.IntegerField(db_index=True)
    reserve_check = models.NullBooleanField(db_index=True)

    # Series and publisher links
    series = models.ForeignKey(Series)
    indicia_publisher = models.ForeignKey(IndiciaPublisher, null=True)
    brand = models.ForeignKey(Brand, null=True)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)
    
    def _display_number(self):
        if self.display_volume_with_number:
            return u'v%s#%s' % (self.volume, self.number)
        return self.number
    display_number = property(_display_number)

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

    def has_format(self):
        return self.size or \
               self.binding or \
               self.paper_stock or \
               self.printing_process

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
        return u'%s #%s' % (self.series, self.display_number)

