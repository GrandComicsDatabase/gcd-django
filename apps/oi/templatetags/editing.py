# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template

from apps.gcd.templatetags.display import absolute_url, show_story_short
from apps.oi.models import RevisionLock, CTYPES, StoryRevision
from apps.oi.coordinators import issue_revision_modified

register = template.Library()

DOC_URL = 'https://docs.comics.org/wiki/'


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

    if changeset.change_type in [CTYPES['publisher'], CTYPES['printer'],
                                 CTYPES['award'], CTYPES['character'],
                                 CTYPES['group'], CTYPES['creator'],
                                 CTYPES['universe'], CTYPES['story_arc']]:
        return absolute_url(revision)
    elif changeset.change_type in [CTYPES['brand_group'],
                                   CTYPES['indicia_publisher'],
                                   CTYPES['indicia_printer']]:
        return mark_safe('%s : %s' % (absolute_url(revision.parent),
                                      absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand']:
        header_link = ''
        if revision.parent:
            return mark_safe('%s : %s' % (absolute_url(revision.parent),
                                          absolute_url(revision)))
        for group in revision.group.all():
            header_link += absolute_url(group) + '; '
        header_link = header_link[:-2]
        return mark_safe('%s : %s' % (header_link, absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand_use']:
        return mark_safe('%s at %s (%s)' % (absolute_url(revision.emblem),
                                            absolute_url(revision.publisher),
                                            revision.year_began))
    elif changeset.change_type == CTYPES['series']:
        if revision.previous() and (revision.previous().publisher !=
                                    revision.publisher):
            publisher_string = '<span class="comparison_highlight">%s</span>'\
              % absolute_url(revision.publisher)
        else:
            publisher_string = absolute_url(revision.publisher)
        return mark_safe('%s (%s)' %
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
        header_link = mark_safe('%s (%s) <a href="%s">%s</a>' % (series_url,
                                                                 pub_url,
                                                                 issue_url,
                                                                 issue_num))
        if changeset.change_type == CTYPES['two_issues']:
            revision = changeset.issuerevisions.all()[1]
            series_url = absolute_url(revision.issue.series)
            pub_url = absolute_url(revision.issue.series.publisher)
            issue_url = revision.issue.get_absolute_url()
            issue_num = revision.issue.display_number
            header_link += mark_safe(' and %s (%s) <a href="%s">%s</a>' %
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
            issue_num = '<a href="%s">%s</a>' % \
                        (revision.issue.get_absolute_url(), issue_num)

        if changeset.issuerevisions.count() > 1:
            # if it was a bulk skeleton, do same for last issue number
            last_revision = \
              changeset.issuerevisions.order_by('-revision_sort_code')[0]
            last_issue_num = last_revision.display_number
            if last_revision.issue:
                last_issue_num = '<a href="%s">%s</a>' % \
                  (last_revision.issue.get_absolute_url(), last_issue_num)
            issue_num = '%s - %s' % (issue_num, last_issue_num)

        return mark_safe('%s (%s) %s' % (series_url, pub_url, issue_num))
    elif changeset.change_type in [CTYPES['feature'], CTYPES['feature_logo']]:
        return mark_safe('%s' % (absolute_url(revision)))
    elif changeset.change_type == CTYPES['image']:
        return absolute_url(revision.object)
    elif changeset.change_type == CTYPES['creator_signature']:
        return mark_safe('%s' % (absolute_url(revision.creator)))
    elif changeset.change_type == CTYPES['creator_art_influence']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.creator),
                          absolute_url(revision)))
    elif changeset.change_type == CTYPES['received_award']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.recipient),
                          absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_membership']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.creator),
                          absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_non_comic_work']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.creator),
                          absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_relation']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.from_creator),
                          absolute_url(revision.to_creator)))
    elif changeset.change_type == CTYPES['creator_school']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.creator),
                          absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_degree']:
        return mark_safe('%s : %s' %
                         (absolute_url(revision.creator),
                          absolute_url(revision)))
    else:
        return ''


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
            return mark_safe("class='text-red-700'")
    # TODO these likely should be treated as above
    elif changeset.change_type not in [CTYPES['issue'],
                                       CTYPES['two_issues'],
                                       CTYPES['variant_add']]:
        changeset.expires = changeset.created + \
          timedelta(weeks=settings.RESERVE_ISSUE_WEEKS)
        if datetime.today() - changeset.created > \
                timedelta(weeks=settings.RESERVE_ISSUE_WEEKS-1):
            return mark_safe("class='text-red-700'")
    elif changeset.issuerevisions.earliest('created').issue and \
      changeset.issuerevisions.earliest('created').issue.revisions\
                                                        .count() > 2:
        if check_for_modified(changeset, settings.RESERVE_ISSUE_WEEKS):
            return mark_safe("class='text-red-700'")
    else:
        if check_for_modified(changeset, settings.RESERVE_ISSUE_INITIAL_WEEKS):
            return mark_safe("class='text-red-700'")
    return ""


@register.filter
def is_locked(object):
    return RevisionLock.objects.filter(
           object_id=object.id,
           content_type=ContentType.objects.get_for_model(object)).first()


@register.filter
def show_doc_link(doc_links, field):
    if field in doc_links:
        return mark_safe(
          ' <a href="%s%s" target=_blank>[?]</a>' % (DOC_URL,
                                                     doc_links[field]))
    else:
        return ""


@register.filter
def show_revision_short(revision, markup=True):
    if revision is None:
        return ''
    if isinstance(revision, StoryRevision):
        return show_story_short(revision, markup=markup)
    return str(revision)


@register.filter
def link_other_reprint(reprint, is_source):
    if is_source:
        if reprint.target:
            text = '<a href="%s">%s</a> <br> of %s' % \
                     (reprint.target.get_absolute_url(),
                      show_story_short(reprint.target),
                      reprint.target.issue.full_name())
        elif reprint.target_issue:
            text = '<a href="%s">%s</a>' % \
                     (reprint.target_issue.get_absolute_url(),
                      reprint.target_issue.full_name())
        else:
            text = '%s' % reprint
    else:
        if reprint.origin:
            text = '<a href="%s">%s</a> <br> of %s' % \
                     (reprint.origin.get_absolute_url(),
                      show_story_short(reprint.origin),
                      reprint.origin.issue.full_name())
        elif reprint.origin_issue:
            text = '<a href="%s">%s</a>' % \
                     (reprint.origin_issue.get_absolute_url(),
                      reprint.origin_issue.full_name())
        else:
            text = '%s' % reprint
    return mark_safe(text)
