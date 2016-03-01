# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.core import urlresolvers

from .gcddata import GcdData
from .issue import Issue


ZOOM_SMALL = 1
ZOOM_MEDIUM = 2
ZOOM_LARGE = 4


class Cover(GcdData):
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
    front_left = models.IntegerField(null=True, blank=True, default=0)
    front_right = models.IntegerField(null=True, blank=True, default=0)
    front_bottom = models.IntegerField(null=True, blank=True, default=0)
    front_top = models.IntegerField(null=True, blank=True, default=0)

    # Fields related to change management.
    last_upload = models.DateTimeField(null=True, db_index=True)

    @property
    def sort_code(self):
        return self.issue.sort_code

    def base_dir(self):
        return (settings.MEDIA_ROOT + settings.COVERS_DIR +
                str(int(self.id/1000)))

    def get_absolute_url(self):
        return urlresolvers.reverse(
            'issue_cover_view',
            kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE})

    def get_base_url(self):
        return (settings.IMAGE_SERVER_URL + settings.COVERS_DIR +
                str(int(self.id / 1000)))

    def get_status_url(self):
        if self.marked:
            return urlresolvers.reverse(
                'replace_cover',
                kwargs={'cover_id': self.id})
        else:
            return urlresolvers.reverse(
                'issue_cover_view',
                kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE})

    def get_cover_status(self):
        if self.marked:
            return 4
        return 3

    def stat_counts(self):
        if self.deleted:
            return {}

        return {
            'covers': 1,
        }

    def delete(self):
        self.marked = False
        super(Cover, self).delete()

    def __unicode__(self):
        return u'%s %s cover' % (self.issue.series, self.issue.display_number)
