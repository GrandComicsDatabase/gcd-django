# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.safestring import mark_safe
import django.urls as urlresolvers
from django.template import engines

import django_tables2 as tables

from .gcddata import GcdLink
from .story import StoryCharacter
from .issue import (Issue, IssueTable, IssuePublisherTable, IssueColumn,
                    VCS_Codes)

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

    def get_cover_color(self):
        if self.marked:
            return 'bg-green-300'
        return 'bg-green-600'

    def delete(self):
        self.deleted = True
        self.marked = False
        self.reserved = False
        self.save()

    def deletable(self):
        return self.revisions.filter(changeset__state__in=states.ACTIVE)\
                             .count() == 0

    def approved_changesets(self):
        from apps.oi.models import Changeset
        revision_ids = self.revisions.values_list('changeset__id', flat=True)
        return Changeset.objects.filter(id__in=revision_ids, state=5)\
                                .order_by('-modified')

    def __str__(self):
        return '%s %s cover' % (self.issue.series, self.issue.display_number)


def box_covers(issue):
    """
    The covers on which the characters of the cover sequence of an issue
    can be marked: those of the issue and those of its variants with only a
    scan difference, which show the same art and use its cover sequence.
    """
    return Cover.objects.filter(
      Q(issue=issue)
      | Q(issue__variant_of=issue,
          issue__variant_cover_status=VCS_Codes.ONLY_SCAN_DIFFERENCE),
      deleted=False)


# Boxes on a cover of box_covers for the issue of their sequence.
VALID_BOX_COVER = Q(cover__deleted=False) & (
  Q(cover__issue=F('story_character__story__issue'))
  | Q(cover__issue__variant_of=F('story_character__story__issue'),
      cover__issue__variant_cover_status=VCS_Codes.ONLY_SCAN_DIFFERENCE))


class CoverCharacterBox(GcdLink):
    """
    The rectangle on the front of a cover that shows a character appearance.

    The box belongs to the appearance of the character in the cover
    sequence, so it follows its universe, deletions and locks.

    Points are in affine coordinates of the front as the cover is scanned,
    with the origin in the top left corner: x in 1/10000 of the width of
    the front, y in 1/10000 of its height.  The character can be printed at
    any angle, so the rectangle can be turned on the front and is stored by
    three of its corners, named as on the upright cut-out (top is the side
    of the head); the fourth corner is top_right + bottom_left - top_left.
    A corner can lie outside the front for a character near its edge, and
    that part of the cut-out stays empty; the centre is on the front and
    both sides are at least 1.  The proportions of the scan the box was
    drawn on are kept in scan_aspect, to show the cut-out undistorted and
    to find the angle again.
    """
    class Meta:
        """One box for an appearance on a cover."""
        app_label = 'gcd'
        db_table = 'gcd_cover_character_box'
        unique_together = ('story_character', 'cover')

    story_character = models.ForeignKey(StoryCharacter,
                                        on_delete=models.CASCADE,
                                        related_name='cover_boxes')
    cover = models.ForeignKey(Cover, on_delete=models.CASCADE,
                              related_name='character_boxes')
    top_left_x = models.SmallIntegerField(
      help_text='x of the top left corner, in 1/10000 of the width of the '
                'front.')
    top_left_y = models.SmallIntegerField(
      help_text='y of the top left corner, in 1/10000 of the height of the '
                'front.')
    top_right_x = models.SmallIntegerField(
      help_text='x of the top right corner, in 1/10000 of the width of the '
                'front.')
    top_right_y = models.SmallIntegerField(
      help_text='y of the top right corner, in 1/10000 of the height of '
                'the front.')
    bottom_left_x = models.SmallIntegerField(
      help_text='x of the bottom left corner, in 1/10000 of the width of '
                'the front.')
    bottom_left_y = models.SmallIntegerField(
      help_text='y of the bottom left corner, in 1/10000 of the height of '
                'the front.')
    scan_date = models.DateTimeField(
      null=True,
      help_text='The last upload of the cover scan the box was drawn on.')
    scan_aspect = models.PositiveIntegerField(
      help_text='Height / width of the scan the box was drawn on, times '
                '10000 (400 x 615 pixels gives 15375).')

    def __str__(self):
        """The character of the box and its cover."""
        return '%s on %s' % (self.story_character.character, self.cover)


# Width and height in pixels of the frame a cut-out fills: the size of a cover
# on the character page, and a size of the same proportions that fits two of
# them side by side with a small gap in it.
BOX_SIZE_LARGE = (200, 304)
BOX_SIZE_SMALL = (98, 149)


def calculate_row_class(**kwargs):
    """ callables will be called with optional keyword arguments record
        and table
    https://django-tables2.readthedocs.io/en/stable/pages/
            column-attributes.html?highlight=row_attrs#row-attributes
    """
    row_attrs = 'w-[154px] md:w-[204px] shadow-md p-[2px] flex flex-col'
    record = kwargs.get("record", None)
    if record and record.marked:
        row_attrs += ' cover-is-marked'

    return row_attrs


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


class CoverIssuePublisherEditTable(IssuePublisherTable):
    cover = tables.Column(accessor='id',
                          verbose_name='', orderable=False)
    issue = IssueColumn(accessor='issue', verbose_name='Issue',
                        template_name='gcd/bits/sortable_issue_entry.html',
                        )
    on_sale_date = tables.Column(accessor='issue__on_sale_date',
                                 verbose_name='On-sale')
    publication_date = tables.Column(accessor='issue__publication_date',
                                     verbose_name='Publication Date')
    edit_cover = tables.Column(accessor='issue', attrs={"div":{"class": "mt-auto"}},
                               verbose_name='', orderable=False)
    publisher = tables.Column(accessor='issue__series__publisher')

    class Meta:
        model = Cover
        fields = ('cover', 'issue', 'publisher', 'publication_date',
                  'on_sale_date', 'edit_cover')
        row_attrs = {'class': calculate_row_class}

    def render_cover(self, record):
        from apps.gcd.views.covers import get_image_tag
        cover_tag = '<a href="%s">%s</a>' % (record.get_absolute_url(),
                                             get_image_tag(record,
                                                           '', 2))
        return mark_safe(cover_tag)

    def render_edit_cover(self, value):
        link = urlresolvers.reverse("edit_covers",
                                    kwargs={'issue_id': value.id})
        return mark_safe('<btn class="btn-blue-editing">'
                         '<a href="%s">%s</a></btn>' % (link,
                                                        'Add / Replace Cover'))

    def render_issue(self, value):
        return mark_safe('<a href="%s">%s (%s series)</a>' % (
          value.get_absolute_url(),
          value.short_name(),
          value.series.year_began))

    def order_issue(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue__series__sort_name',
                                       'issue__series__year_began',
                                       'issue__series__id',
                                       direction + 'issue__sort_code')
        return (query_set, True)

    def order_publisher(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(
          direction + 'issue__series__publisher__name',
          direction + 'issue__series__sort_name',
          direction + 'issue__sort_code')
        return (query_set, True)

    def order_publication_date(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue__key_date',
                                       direction + 'issue__series__sort_name',
                                       direction + 'issue__sort_code')
        return (query_set, True)

    def order_on_sale_date(self, query_set, is_descending):
        direction = '-' if is_descending else ''
        query_set = query_set.order_by(direction + 'issue__on_sale_date',
                                       direction + 'issue__series__sort_name',
                                       direction + 'issue__sort_code')
        return (query_set, True)


class OnSaleCoverIssueTable(CoverIssuePublisherEditTable):
    publisher = None

    class Meta:
        model = Cover
        fields = ('cover', 'issue', 'publication_date', 'on_sale_date',
                  'edit_cover')
        row_attrs = {'class': calculate_row_class}

    def render_issue(self, value):
        return mark_safe('<a href="%s">%s</a>' % (value.get_absolute_url(),
                                                  value.full_name()))


class CoverSeriesTable(CoverIssuePublisherEditTable):
    publisher = None

    class Meta:
        model = Cover
        fields = ('cover', 'issue', 'publication_date', 'on_sale_date',
                  'edit_cover')
        row_attrs = {'class': calculate_row_class}

    def render_issue(self, value):
        return mark_safe('<a href="%s">%s</a>' % (value.get_absolute_url(),
                                                  value.full_descriptor))


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
