from django.db import models
from country import Country
from django.core.exceptions import ObjectDoesNotExist

class Publisher(models.Model):
    class Meta:
        ordering = ['name']
        app_label = 'gcd'

    # Core publisher fields.
    name = models.CharField(max_length=255, db_index=True)
    year_began = models.IntegerField(db_index=True, null=True)
    year_ended = models.IntegerField(null=True)
    country = models.ForeignKey(Country)
    notes = models.TextField(null=True)
    url = models.URLField(null=True)

    # Cached counts.
    imprint_count = models.IntegerField()
    series_count = models.IntegerField()
    issue_count = models.IntegerField()

    # Fields about relating publishers/imprints to each other.
    is_master = models.BooleanField(db_index=True)
    parent = models.ForeignKey('self', null=True,
                               related_name='imprint_set')

    # Fields related to change management.
    reserved = models.BooleanField(default=0, db_index=True)
    created = models.DateField(auto_now_add=True)
    modified = models.DateField(auto_now=True)

    def __unicode__(self):
        return self.name

    def has_imprints(self):
        return self.imprint_set.count() > 0

    def is_imprint(self):
        return self.parent_id is not None and self.parent_id != 0

    def get_absolute_url(self):
        if self.is_imprint():
            return "/imprint/%i/" % self.id
        else:
            return "/publisher/%i/" % self.id

    def get_official_url(self):
        try:
            if not self.url.lower().startswith("http://"):
                self.url = "http://" + self.url
                #TODO: auto fix urls ?
                #self.save()
        except:
            return ""

        return self.url

    def get_full_name(self):
        if self.is_imprint():
            if self.parent_id:
                return '%s: %s' % (self.parent.name, self.name)
            return '*GCD ORPHAN IMPRINT: %s' % (self.name)
        return self.name

    def __unicode__(self):
        return self.name

    def computed_issue_count(self):
        # issue_count is not accurate, but computing is slow.
        return self.issue_count or 0

        # This is more accurate, but too slow right now.
        # Would be better to properly maintain issue_count.
        # num_issues = 0
        # for series in self.series_set.all():
        #     num_issues += series.issue_set.count()
        # return num_issues

