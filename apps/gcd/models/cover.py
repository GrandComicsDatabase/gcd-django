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
    has_image = models.BooleanField(default=0)
    marked = models.BooleanField(default=0)
    limit_display = models.BooleanField(default=0)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)
    last_upload = models.DateTimeField(null=True)

    def base_dir(self):
        return settings.MEDIA_ROOT + settings.COVERS_DIR + \
          str(int(self.id/1000))

    def get_absolute_url(self):
        return urlresolvers.reverse('issue_cover_view', 
                kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE } )

    def get_status_url(self):
        if self.marked and self.has_image:
            return urlresolvers.reverse(
                'replace_cover',
                kwargs={'cover_id': self.id} )
        elif self.has_image:
            return urlresolvers.reverse(
		'issue_cover_view', 
                kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE } )
        else:
            return urlresolvers.reverse(
                'upload_cover',
                kwargs={'issue_id': self.issue.id} )

    def get_cover_status(self):
        import logging
        if self.marked:
            return 4
        if self.has_image:
            return 3
        return 0

