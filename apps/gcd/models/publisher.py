from django.db import models
from country import Country

class Publisher(models.Model):
    class Meta:
        db_table = 'publishers'
        ordering = ['name']

    class Admin:
        pass

    id = models.AutoField(primary_key = True, db_column = 'ID')

    # Core publisher fields.
    name = models.CharField(max_length = 255, db_column = 'PubName',
                            null = True)
    year_began = models.IntegerField(db_column = 'YearBegan', null = True)
    year_ended = models.IntegerField(db_column = 'YearEnded', null = True)
    country = models.ForeignKey(Country, db_column = 'CountryID', null = True)
    notes = models.TextField(db_column = 'Notes', null = True)
    url = models.TextField(db_column = 'web', null = True)

    # This seems to help sort related publishers together despite spelling.
    alpha_sort_code = models.CharField(max_length = 1,
                                       db_column = 'AlphaSortCode', null = True)

    # I'm not convinced we need all of these cached counts.
    # They're not entirely accurate in the current DB snapshot.
    imprint_count = models.IntegerField(db_column = 'ImprintCount', null = True)
    series_count = models.IntegerField(db_column = 'BookCount', null = True)
    issue_count = models.IntegerField(db_column = 'IssueCount', null = True)

    # Fields about relating publishers to each other.  Not sure about
    # connection as it is always null except one '' right now.  But perhaps
    # it is intended to describe these relationships (imprint, common name...)
    # next_id is completely mysterious, but maybe in this category?
    is_master = models.NullBooleanField(db_column = 'Master', null = True)
    connection = models.TextField(db_column = 'Connection', null = True)
    parent = models.ForeignKey('self', db_column = 'ParentID',
                                null = True, related_name = 'imprint_set')
    next = models.ForeignKey('self', db_column = 'NextID', null = True,
                             related_name = 'previous_set')

    # Fields related to change management.
    # No idea what the distinction between "Updated" and "Modified" is.
    created = models.DateField(auto_now_add = True, null = True)
    modified = models.DateField(db_column = 'Modified',
                                auto_now = True, null = True)
    updated = models.DateField(db_column = 'Updated',
                               auto_now = True, null = True)

    def __str__(self):
        return self.name

    def has_imprints(self):
        return self.imprint_set.count > 0

    def computed_issue_count(self):
        # issue_count is not accurate, but computing is slow.
        return self.issue_count or 0

        # This is more accurate, but too slow right now.
        # Would be better to properly maintain issue_count.
        # num_issues = 0
        # for series in self.series_set.all():
        #     num_issues += series.issue_set.count()
        # return num_issues

