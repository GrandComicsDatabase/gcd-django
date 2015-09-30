# -*- coding: utf-8 -*-
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template

from apps.gcd.templatetags.display import absolute_url
from apps.oi.models import CTYPES

register = template.Library()

def header_link(changeset):
    if changeset.inline():
        revision = changeset.inline_revision()
    else:
        if changeset.issuerevisions.count():
            revision = changeset.issuerevisions.all()[0]
        elif changeset.change_type == CTYPES['series_bond']:
            revision = changeset.seriesbondrevisions.get()
        elif changeset.change_type == CTYPES['creators']:
            revision = changeset.creatorrevisions.get()
        elif changeset.change_type == CTYPES['creator_membership']:
            revision = changeset.creatormembershiprevisions.all()[0]
        elif changeset.change_type == CTYPES['creator_award']:
            revision = changeset.creatorawardrevisions.all()[0]
        elif changeset.change_type == CTYPES['creator_artinfluence']:
            revision = changeset.creatorartinfluencerevisions.all()[0]
        elif changeset.change_type == CTYPES['creator_noncomicwork']:
            revision = changeset.creatornoncomicworkrevisions.all()[0]
        else:
            raise NotImplementedError

    if changeset.change_type == CTYPES['publisher']:
        return absolute_url(revision)
    elif changeset.change_type == CTYPES['brand_group'] or \
         changeset.change_type == CTYPES['indicia_publisher']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.parent), absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand']:
        header_link = u''
        if revision.parent:
            return mark_safe(u'%s : %s' %
                            (absolute_url(revision.parent), absolute_url(revision)))
        for group in revision.group.all():
            header_link += absolute_url(group) + '; '
        header_link = header_link[:-2]
        return mark_safe(u'%s : %s' % (header_link, absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand_use']:
        return mark_safe(u'%s at %s (%s)' % (absolute_url(revision.emblem),
                                             absolute_url(revision.publisher),
                                             revision.year_began))
    elif changeset.change_type == CTYPES['series']:
        if revision.previous() and revision.previous().publisher != revision.publisher:
            publisher_string = u'<span class="comparison_highlight">%s</span>'\
              % absolute_url(revision.publisher)
        else:
            publisher_string = absolute_url(revision.publisher)
        return mark_safe(u'%s (%s)' %
                         (absolute_url(revision), publisher_string))
    elif changeset.change_type in [CTYPES['cover'], CTYPES['issue'],
                                   CTYPES['variant_add'], CTYPES['two_issues']]:
        if changeset.change_type == CTYPES['variant_add']:
            # second issue revision is base issue and does exist in any case
            revision = changeset.issuerevisions.all()[1]
        if changeset.change_type == CTYPES['two_issues']:
            revision = changeset.issuerevisions.all()[0]
        series_url = absolute_url(revision.issue.series)
        pub_url = absolute_url(revision.issue.series.publisher)
        issue_url = revision.issue.get_absolute_url()
        issue_num = revision.issue.display_number
        header_link = mark_safe(u'%s (%s) <a href="%s">%s</a>' %
                        (series_url, pub_url, issue_url, issue_num))
        if changeset.change_type == CTYPES['two_issues']:
            revision = changeset.issuerevisions.all()[1]
            series_url = absolute_url(revision.issue.series)
            pub_url = absolute_url(revision.issue.series.publisher)
            issue_url = revision.issue.get_absolute_url()
            issue_num = revision.issue.display_number
            header_link += mark_safe(u' and %s (%s) <a href="%s">%s</a>' %
                            (series_url, pub_url, issue_url, issue_num))
        if changeset.change_type == CTYPES['cover']:
            if revision.issue.variant_name:
                header_link += mark_safe(' [%s]' % \
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
    elif changeset.change_type == CTYPES['creator_membership']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_award']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_artinfluence']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    elif changeset.change_type == CTYPES['creator_noncomicwork']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.creator), absolute_url(revision)))
    else:
        return u''

register.filter(header_link)
