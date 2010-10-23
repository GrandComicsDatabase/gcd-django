# -*- coding: utf-8 -*-
from django.db import models, settings
from django.core import urlresolvers

from issue import Issue

ZOOM_SMALL = 1
ZOOM_MEDIUM = 2
ZOOM_LARGE = 4

class Cover(models.Model):
    class Meta:
        app_label = 'gcd'
        ordering = ['issue']
        get_latest_by = "id"
        permissions = (
            ('can_upload_cover', 'can upload cover'),
        )

    # Cover belongs to an issue
    issue = models.ForeignKey(Issue)

    # Fields directly related to cover images
    marked = models.BooleanField(default=False)
    limit_display = models.BooleanField(default=False)
    is_wraparound = models.BooleanField(default=False)
    front_left = models.IntegerField(default=0)
    front_right = models.IntegerField(default=0)
    front_bottom = models.IntegerField(default=0)
    front_top = models.IntegerField(default=0)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)
    last_upload = models.DateTimeField(null=True)

    deleted = models.BooleanField(default=0, db_index=True)

    def _sort_code(self):
        return self.issue.sort_code
    sort_code = property(_sort_code)

    def base_dir(self):
        return settings.MEDIA_ROOT + settings.COVERS_DIR + \
          str(int(self.id/1000))

    def get_absolute_url(self):
        return urlresolvers.reverse('issue_cover_view', 
                kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE } )

    def get_status_url(self):
        if self.marked:
            return urlresolvers.reverse(
                'replace_cover',
                kwargs={'cover_id': self.id} )
        else:
            return urlresolvers.reverse(
                'issue_cover_view', 
                kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE } )

    def get_cover_status(self):
        import logging
        if self.marked:
            return 4
        return 3

    def delete(self):
        self.deleted = True
        self.marked = False
        self.save()
