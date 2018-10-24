# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template

from apps.gcd.templatetags.display import absolute_url
from apps.oi.models import RevisionLock, CTYPES
from apps.oi.coordinators import issue_revision_modified

register = template.Library()


@register.filter
def header_link(changeset):
    if changeset.inline():
        revision = changeset.inline_revision()
    else:
        if changeset.issuerevisions.count():
            revision = changeset.issuerevisions.all()[0]
        elif changeset.change_type == CTYPES['series_bond']:
            revision = changeset.seriesbondrevisions.get()
        else:
            raise NotImplementedError

    if changeset.change_type == CTYPES['publisher']:
        return absolute_url(revision)
    elif changeset.change_type == CTYPES['brand_group'] or \
            changeset.change_type == CTYPES['indicia_publisher']:
        return mark_safe(u'%s : %s' % (absolute_url(revision.parent),
                                       absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand']:
        header_link = u''
        if revision.parent:
            return mark_safe(u'%s : %s' % (absolute_url(revision.parent),
                                           absolute_url(revision)))
        for group in revision.group.all():
            header_link += absolute_url(group) + '; '
        header_link = header_link[:-2]
        return mark_safe(u'%s : %s' % (header_link, absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand_use']:
        return mark_safe(u'%s at %s (%s)' % (absolute_url(revision.emblem),
                                             absolute_url(revision.publisher),
                                             revision.year_began))
    elif changeset.change_type == CTYPES['series']:
        if revision.previous() and (revision.previous().publisher !=
                                    revision.publisher):
            publisher_string = u'<span class="comparison_highlight">%s</span>'\
              % absolute_url(revision.publisher)
        else:
            publisher_string = absolute_url(revision.publisher)
        return mark_safe(u'%s (%s)' %
                         (absolute_url(revision), publisher_string))
    elif changeset.change_type in [CTYPES['cover'],
                                   CTYPES['issue'],
                                   CTYPES['variant_add'],
                                   CTYPES['two_issues']]:
        if changeset.change_type == CTYPES['variant_add']:
            # second issue revision is base issue and does exist in any case
            revision = changeset.issuerevisions.all()[1]
        if changeset.change_type == CTYPES['two_issues']:
            revision = changeset.issuerevisions.all()[0]
        series_url = absolute_url(revision.issue.series)
        pub_url = absolute_url(revision.issue.series.publisher)
        issue_url = revision.issue.get_absolute_url()
        issue_num = revision.issue.display_number
        header_link = mark_safe(u'%s (%s) <a href="%s">%s</a>' % (series_url,
                                                                  pub_url,
                                                                  issue_url,
                                                                  issue_num))
        if changeset.change_type == CTYPES['two_issues']:
            revision = changeset.issuerevisions.all()[1]
            series_url = absolute_url(revision.issue.series)
            pub_url = absolute_url(revision.issue.series.publisher)
            issue_url = revision.issue.get_absolute_url()
            issue_num = revision.issue.display_number
            header_link += mark_safe(u' and %s (%s) <a href="%s">%s</a>' %
                                     (series_url, pub_url,
                                      issue_url, issue_num)
                                     )
        if changeset.change_type == CTYPES['cover']:
            if revision.issue.variant_name:
                header_link += mark_safe(' [%s]' %
                                         esc(revision.issue.variant_name))
        if changeset.change_type == CTYPES['issue']:
            if revision.variant_name:
                header_link += mark_safe(' [%s]' % esc(revision.variant_name))
        return header_link

    elif changeset.change_type == CTYPES['issue_add']:
        series_url = absolute_url(revision.series)
        pub_url = absolute_url(revision.series.publisher)

        # get first skeleton's display num
        revision = changeset.issuerevisions.order_by('revision_sort_code')[0]
        issue_num = revision.display_number
        if revision.issue:
            # if it's been approved, make it a link to real issue
            issue_num = u'<a href="%s">%s</a>' % \
                        (revision.issue.get_absolute_url(), issue_num)

        if changeset.issuerevisions.count() > 1:
            # if it was a bulk skeleton, do same for last issue number
            last_revision = \
              changeset.issuerevisions.order_by('-revision_sort_code')[0]
            last_issue_num = last_revision.display_number
            if last_revision.issue:
                last_issue_num = u'<a href="%s">%s</a>' % \
                  (last_revision.issue.get_absolute_url(), last_issue_num)
            issue_num = u'%s - %s' % (issue_num, last_issue_num)

        return mark_safe(u'%s (%s) %s' % (series_url, pub_url, issue_num))
    elif changeset.change_type == CTYPES['image']:
        return absolute_url(revision.object)
    elif changeset.change_type == CTYPES['award']:
        return mark_safe(u'%s' % (absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator']:
        return mark_safe(u'%s' % (absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_art_influence']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_award']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_membership']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_non_comic_work']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_relation']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.from_creator),
                          absolute_url(revision.to_creator)))
    elif changeset.change_type == CTYPES['creator_school']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_degree']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    else:
        return u''


def check_for_modified(changeset, clearing_weeks):
    # at least another week to go
    if datetime.today() - changeset.created < \
       timedelta(weeks=clearing_weeks-1):
        changeset.expires = changeset.created + \
          timedelta(weeks=clearing_weeks)
        return False
    # at max three weeks extensions
    if datetime.today() - changeset.created > \
       timedelta(weeks=clearing_weeks+2):
        changeset.expires = changeset.created + \
          timedelta(weeks=clearing_weeks+3)
        return True
    # was there an edit to the issue in the last week
    modified = issue_revision_modified(changeset)
    if modified > changeset.created + \
       timedelta(weeks=clearing_weeks-1):
        changeset.expires = modified + timedelta(weeks=1)
    else:
        # in last week with no recent changes
        changeset.expires = changeset.created + \
            timedelta(weeks=clearing_weeks)
    return True


@register.filter
def is_overdue(changeset):
    # TODO touch this after the changeset refactor
    if changeset.change_type in [CTYPES['publisher'],
                                 CTYPES['brand'],
                                 CTYPES['indicia_publisher'],
                                 CTYPES['series']]:
        changeset.expires = changeset.created + \
          timedelta(days=settings.RESERVE_NON_ISSUE_DAYS)
        if datetime.today() - changeset.created > \
                timedelta(days=settings.RESERVE_NON_ISSUE_DAYS/2):
            return mark_safe("class='overdue'")
    # TODO these likely should be treated as above
    elif changeset.change_type not in [CTYPES['issue'],
                                       CTYPES['two_issues'],
                                       CTYPES['variant_add']]:
        changeset.expires = changeset.created + \
          timedelta(weeks=settings.RESERVE_ISSUE_WEEKS)
        if datetime.today() - changeset.created > \
                timedelta(weeks=settings.RESERVE_ISSUE_WEEKS-1):
            return mark_safe("class='overdue'")
    elif changeset.issuerevisions.earliest('created').issue and \
      changeset.issuerevisions.earliest('created').issue.revisions\
                                                           .count() > 2:
        if check_for_modified(changeset, settings.RESERVE_ISSUE_WEEKS):
            return mark_safe("class='overdue'")
    else:
        if check_for_modified(changeset, settings.RESERVE_ISSUE_INITIAL_WEEKS):
            return mark_safe("class='overdue'")
    return ""


@register.filter
def is_locked(object):
    return RevisionLock.objects.filter(
           object_id=object.id,
           content_type=ContentType.objects.get_for_model(object)).first()
