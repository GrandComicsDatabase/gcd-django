# -*- coding: utf-8 -*-
from django.db import models
from django.core import urlresolvers

from issue import Issue
from series import Series

class Cover(models.Model):
    """ cover from gcd database"""

    class Meta:
        db_table = 'covers'
        app_label = 'gcd'
        ordering = ['code']
        permissions = (
            ('can_upload_cover', 'can upload cover'),
        )

    class Admin:
        pass

    id = models.AutoField(primary_key = True, db_column = 'ID')

    # Attributes from publishers table.  For some reason only the name
    # is entered here, with no traditional foreign key id.
    publisher_name = models.CharField(max_length = 255, db_column = 'Pub_Name',
                                      null = True)
    # Series attributes
    
    series = models.ForeignKey(Series,
                               db_column = 'SeriesID')
    series_name = models.CharField(max_length = 255, db_column = 'Bk_Name',
                                   null = True)
    year_began = models.IntegerField(db_column = 'Yr_Began', null = True)

    # Issue attributes
    issue = models.OneToOneField(Issue,
                                 db_column = 'IssueID')
    issue_number = models.CharField(max_length = 50, db_column = 'Issue')

    # Fields directly related to cover images
    code = models.CharField(db_column = 'covercode', max_length = 50)
    has_image = models.BooleanField(db_column = 'HasImage')
    marked = models.NullBooleanField(db_column = 'Marked')
    variant_text = models.CharField(max_length = 255, null = True)

    # Probably want to rename this.  "num_covers" to match usage elsewhere?
    covers_this_title = models.IntegerField(db_column = 'CoversThisTitle',
                                            null = True)

    # This is probably a NullBoolean, but not 100% certain.  Only 0 and NULL.
    coverage = models.IntegerField(db_column = 'Coverage', null= True)
    is_master = models.IntegerField(null = True)
    variant_code = models.CharField(max_length = 2, null = True)
    server_version = models.IntegerField(db_column = 'gfxserver')
    count = models.IntegerField(db_column = 'Count', null = True)
    contributor = models.CharField(max_length = 255, null = True)

    # Fields related to change management.
    created = models.DateTimeField(db_column = 'Created',
                                   auto_now_add = True, null = True)
    modified = models.DateTimeField(db_column = 'Modified', null = True)

    def get_status_url(self):
        if self.marked or not self.has_image:
            return urlresolvers.reverse(
                'apps.gcd.views.covers.cover_upload',
                kwargs={'issue_id': self.issue.id} )
        else:
            return self.issue.get_absolute_url()

    def get_cover_status(self):
        import logging
        if self.marked:
            return 4
        if self.has_image:
            return 3
        return 0
