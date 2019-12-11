# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import models
from django.core import urlresolvers

from .issue import Issue

# TODO: should not be importing oi app into gcd app, dependency should be
# the other way around.  Probably.
from apps.oi import states

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
    front_left = models.IntegerField(null=True, blank=True, default=0)
    front_right = models.IntegerField(null=True, blank=True, default=0)
    front_bottom = models.IntegerField(null=True, blank=True, default=0)
    front_top = models.IntegerField(null=True, blank=True, default=0)

    # Fields related to change management.
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)
    last_upload = models.DateTimeField(null=True, db_index=True)

    reserved = models.BooleanField(default=False, db_index=True)
    deleted = models.BooleanField(default=False, db_index=True)

    @property
    def sort_code(self):
        return self.issue.sort_code

    def base_dir(self):
        return settings.MEDIA_ROOT + settings.COVERS_DIR + \
          str(int(self.id/1000))

    def get_absolute_url(self):
        return urlresolvers.reverse('issue_cover_view', 
                kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE } )

    def get_base_url(self):
        return settings.IMAGE_SERVER_URL + settings.COVERS_DIR + \
          str(int(self.id/1000))

    def get_status_url(self):
        if self.marked and not settings.NO_OI and not settings.MYCOMICS:
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
        self.reserved = False
        self.save()

    def deletable(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE).count() == 0

    def __str__(self):
        return '%s %s cover' % (self.issue.series, self.issue.display_number)
