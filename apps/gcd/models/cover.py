# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import models
from django.utils.safestring import mark_safe
import django.urls as urlresolvers
from django.template import engines

import django_tables2 as tables

from .issue import Issue, IssueTable, IssuePublisherTable, IssueColumn

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
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE)

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
        return urlresolvers.reverse(
          'issue_cover_view',
          kwargs={'issue_id': self.issue.id, 'size': ZOOM_LARGE})

    def get_base_url(self, image_server_url=settings.IMAGE_SERVER_URL):
        return image_server_url + settings.COVERS_DIR + \
          str(int(self.id/1000))

    def get_status_url(self):
        if self.marked and not settings.NO_OI and not settings.MYCOMICS:
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

    def delete(self):
        self.deleted = True
        self.marked = False
        self.reserved = False
        self.save()

    def deletable(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE)\
                             .count() == 0

    def __str__(self):
        return '%s %s cover' % (self.issue.series, self.issue.display_number)


class CoverColumn(tables.Column):
    def value(self, value):
        for cover in value:
            return cover

    def render(self, value):
        from apps.gcd.views.covers import get_image_tag
        cover_tag = ''
        for cover in value:
            cover_tag += '<a href="%s">%s</a>' % (cover.get_absolute_url(),
                                                  get_image_tag(cover,
                                                                '', 1.5))
        return mark_safe(cover_tag)


class CoverIssuePublisherTable(IssuePublisherTable):
    cover = CoverColumn(accessor='active_covers',
                        verbose_name='Cover', orderable=False)
    issue = IssueColumn(accessor='id', verbose_name='Issue',
                        template_name='gcd/bits/sortable_issue_overview.html',
                        )

    class Meta:
        model = Issue
        fields = ('cover', 'publisher', 'issue', 'publication_date',
                  'on_sale_date')
        attrs = {'th': {'class': "non_visited"}}


class CoverIssueStoryTable(IssueTable):
    cover = CoverColumn(accessor='active_covers',
                        verbose_name='Cover', orderable=False)
    issue = IssueColumn(accessor='id', verbose_name='Issue',
                        template_name='gcd/bits/sortable_issue_overview.html',
                        )
    longest_story = tables.Column(
      accessor='longest_story_id', verbose_name='Longest Story',
      orderable=False, empty_values=[])

    class Meta:
        model = Issue
        fields = ('cover', 'issue', 'longest_story', 'publication_date',
                  'on_sale_date')
        attrs = {'th': {'class': "non_visited"}}

    def value_longest_story(self, value, record):
        from .story import Story
        if not value:
            if record.variant_of:
                story = record.variant_of.active_stories()\
                              .filter(type_id=19, deleted=False)\
                              .prefetch_related('credits__creator__creator')\
                              .order_by('-page_count')
                if story:
                    story = story[0]
                else:
                    return None
            else:
                return None
        else:
            story = Story.objects.get(id=value)
        return story

    def render_longest_story(self, value, record):
        from .story import Story
        template_name = 'gcd/bits/story_overview.html'
        if not value:
            if record.variant_of:
                story = record.variant_of.active_stories()\
                              .filter(type_id=19, deleted=False)\
                              .prefetch_related('credits__creator__creator')\
                              .order_by('-page_count')
                if story:
                    story = story[0]
                else:
                    return '—'
            else:
                return '—'
        else:
            story = Story.objects.prefetch_related(
              'credits__creator__creator').get(id=value)

        request_context = self.context
        context = {'story': story,
                   'ICON_SET_SYMBOLIC': request_context['ICON_SET_SYMBOLIC']}

        django_engine = engines['django']
        template = django_engine.get_template(template_name)
        rendered_output = template.render(context)

        return rendered_output


class CoverIssueStoryPublisherTable(IssuePublisherTable, CoverIssueStoryTable):
    publication_date = None

    class Meta:
        model = Issue
        fields = ('cover', 'publisher', 'issue', 'longest_story',
                  'on_sale_date')
