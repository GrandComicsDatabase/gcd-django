# -*- coding: utf-8 -*-
from decimal import Decimal
from datetime import datetime, timedelta

from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template
from django.template.defaultfilters import title

from apps.oi.models import StoryRevision, CTYPES
from apps.gcd.templatetags.credits import show_page_count, format_page_count, \
                                          split_reprint_string
from apps.gcd.models.publisher import IndiciaPublisher, Brand, BrandGroup, Publisher
from apps.gcd.models.series import Series
from apps.gcd.models.issue import Issue
from apps.gcd.models.cover import Cover
from apps.gcd.models.image import Image
from apps.gcd.models.seriesbond import SeriesBond, BOND_TYPES
from apps.gcd.views.covers import get_image_tag

register = template.Library()

def absolute_url(item, additional=''):
    if item is not None and hasattr(item, 'get_absolute_url'):
        if additional:
            return mark_safe(u'<a href="%s" %s>%s</a>' %
                             (item.get_absolute_url(), additional, esc(item)))
        else:
            return mark_safe(u'<a href="%s">%s</a>' %
                             (item.get_absolute_url(), esc(item)))
    return ''

def cover_image_tag(cover, size_alt_text):
    size, alt_text = size_alt_text.split(',')
    return get_image_tag(cover, alt_text, int(size))

def show_story_short(story, no_number=False, markup=True):
    if no_number:
        story_line = u''
    else:
        story_line = u'%s.' % story.sequence_number

    if story.title:
        if story.title_inferred:
            title = u'[%s]' % esc(story.title)
        else:
            title = esc(story.title)
    else:
        if markup:
            title = '<span class="no_data">no title</span>'
        else:
            title = 'no title'
    if story.feature:
        story_line = u'%s %s (%s)' % (esc(story_line), title,
                                      esc(story.feature))
    else:
        if markup:
            story_line = u'%s %s (%s)' % (esc(story_line), title,
                                    '<span class="no_data">no feature</span>')
        else:
            story_line = u'%s %s (no feature)' % (esc(story_line), title)

    story_line = u'%s %s' % (story_line, story.type)
    page_count = show_page_count(story)
    if page_count:
        story_line += ', %sp' % page_count
    else:
        if markup:
            story_line += '<span class="no_data"> no page count</span>'
        else:
            story_line += 'no page count'
    return mark_safe(story_line)

def show_revision_short(revision, markup=True):
    if revision is None:
        return u''
    if isinstance(revision, StoryRevision):
        return show_story_short(revision, markup=markup)
    return unicode(revision)

def show_volume(issue):
    if issue.no_volume:
        return u''
    if issue.volume == '':
        return u'?'
    return issue.volume

def show_issue(issue):
    if issue.display_number:
        issue_number = '#%s' % (esc(issue.display_number))
    else:
        issue_number = ''
    if issue.variant_name:
        issue_number = '%s [%s]' % (issue_number, esc(issue.variant_name))
    if issue_number:
        issue_number = '<a href="%s">%s</a>' % (issue.get_absolute_url(),
                                                issue_number)
    return mark_safe('<a href="%s">%s</a> (%s series) %s' %
                     (issue.series.get_absolute_url(),
                      esc(issue.series.name),
                      esc(issue.series.year_began),
                      issue_number))

def show_series_tracking(series, direction):
    target_tracking = series.to_series_bond.filter(\
                        bond_type__id=BOND_TYPES['tracking'])
    origin_tracking = series.from_series_bond.filter(\
                        bond_type__id=BOND_TYPES['tracking'])
    tracking_line = ""
    if direction == 'in' and target_tracking.count():
        for target_series in target_tracking.all():
            if target_series.target_issue:
                tracking_line += "<li> numbering continues with %s" % \
                  target_series.target_issue.full_name_with_link()
            else:
                tracking_line += "<li> numbering continues in %s" % \
                  target_series.target.full_name_with_link()
    elif direction == 'from' and origin_tracking .count():
        for origin_series in origin_tracking.all():
            if origin_series.origin_issue:
                tracking_line += "<li> numbering continued from %s" % \
                  origin_series.origin_issue.full_name_with_link()
            else:
                tracking_line += "<li> numbering continues from %s" % \
                  origin_series.origin.full_name_with_link()
    return mark_safe(tracking_line)

def show_indicia_pub(issue):
    if issue.indicia_publisher is None:
        if issue.indicia_pub_not_printed:
            ip_url = u'[none printed]'
        else:
            ip_url = u'?'
    else:
        ip_url = u'<a href=\"%s\">%s</a>' % \
          (issue.indicia_publisher.get_absolute_url(), issue.indicia_publisher)
        if issue.indicia_pub_not_printed:
            ip_url += u' [not printed on item]'
    return mark_safe(ip_url)

def show_revision_type(cover):
    if cover.deleted:
        return u'[DELETED]'
    if cover.cover:
        if cover.cover.marked:
            return u'[REPLACEMENT]'
        else:
            return u'[SUGGESTED REPLACEMENT]'
    if cover.changeset.issuerevisions.count():
        return u'[VARIANT]'
    if cover.issue.has_covers():
        return u'[ADDITIONAL]'
    return u'[ADDED]'

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
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.parent), absolute_url(revision)))
    elif changeset.change_type == CTYPES['brand']:
        header_link = u''
        # TODO add once migration is correctly done, i.e. parent can be Null
        #if revision.parent:
            #return mark_safe(u'%s : %s' %
                            #(absolute_url(revision.parent), absolute_url(revision)))
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
        header_link = mark_safe(u'%s (%s) <a href="%s">#%s</a>' %
                         (series_url, pub_url, issue_url, issue_num))
        if changeset.change_type == CTYPES['two_issues']:
            revision = changeset.issuerevisions.all()[1]
            series_url = absolute_url(revision.issue.series)
            pub_url = absolute_url(revision.issue.series.publisher)
            issue_url = revision.issue.get_absolute_url()
            issue_num = revision.issue.display_number
            header_link += mark_safe(u' and %s (%s) <a href="%s">#%s</a>' %
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
    else:
        return u''

def compare_field_between_revs(field, rev, prev_rev):
    old = getattr(prev_rev, field)
    new = getattr(rev, field)
    if type(new) == unicode:
        field_changed = old.strip() != new.strip()
    else:
        field_changed = old != new
    return field_changed

# get a human readable list of fields changed in a given approved changeset
def changed_fields(changeset, object):
    object_class = type(object)
    if object_class is Issue:
        revision = changeset.issuerevisions.all().get(issue=object.id)
    elif object_class is Series:
        revision = changeset.seriesrevisions.all().get(series=object.id)
    elif object_class is SeriesBond:
        revision = changeset.seriesbondrevisions.all().get(series_bond=object.id)
    elif object_class is Publisher:
        revision = changeset.publisherrevisions.all().get(publisher=object.id)
    elif object_class is Brand:
        revision = changeset.brandrevisions.all().get(brand=object.id)
    elif object_class is BrandGroup:
        revision = changeset.brandgrouprevisions.all().get(brand_group=object.id)
    elif object_class is IndiciaPublisher:
        revision = changeset.indiciapublisherrevisions.all()\
                            .get(indicia_publisher=object.id)
    elif object_class in [Cover, Image]:
        return ""

    prev_rev = revision.previous()
    changed_list = []
    if prev_rev is None:
        # there was no previous revision so only list the initial add of the object.
        # otherwise too many fields to list.
        changed_list = [u'%s added' % title(revision.source_name.replace('_', ' '))]
    elif revision.deleted:
        changed_list = [u'%s deleted' %
                        title(revision.source_name.replace('_', ' '))]
    else:
        for field in revision._field_list():
            if field == 'after':
                # most ignorable fields handled in oi/view.py/compare()
                # but this one should also be ignored on the initial change
                # history page. the only time it's relevant the line will
                # read "issue added"
                continue
	    if compare_field_between_revs(field, revision, prev_rev):
                changed_list.append(field_name(field))
    return ", ".join(changed_list)

# get a bulleted list of changes at the sequence level
def changed_story_list(changeset):
    if changeset.issuerevisions.count() and \
      changeset.change_type != CTYPES['issue_bulk']:
        # only relevant for single issue changesets
        story_revisions = changeset.storyrevisions.all().order_by('sequence_number')
    else:
        return u''

    output = u''
    if story_revisions.count() > 0:
        for story_revision in story_revisions:
            prev_story_rev = story_revision.previous()
            story_changed_list = []
            if prev_story_rev is None:
                story_changed_list = [u'Sequence added']
            elif story_revision.deleted:
                story_changed_list = [u'Sequence deleted']
            else:
                for field in story_revision._field_list():
                    if compare_field_between_revs(field, story_revision,
                                                  prev_story_rev):
                        story_changed_list.append(field_name(field))
            if story_changed_list:
                output += u'<li>Sequence %s : %s' % \
                          (story_revision.sequence_number,
                           ", ".join(story_changed_list))
        if output is not u'':
            output = u'<ul>%s</ul>' % output
    return mark_safe(output)

def sum_page_counts(stories):
    """
    Return the sum of the story page counts.
    """
    count = Decimal(0)
    for story in stories:
        if story.page_count and not story.deleted:
            count += story.page_count
    return count

# translate field name into more human friendly name
def field_name(field):
    if field in ['is_current', 'is_surrogate']:
        return u'%s?' % title(field.replace(u'is_', u''))
    elif field in ['url', 'isbn']:
        return field.upper()
    elif field == 'after':
        return u'Add Issue After'
    elif field == 'indicia_pub_not_printed':
        return u'Indicia Publisher Not Printed'
    elif field == 'title_inferred':
        return u'Unofficial Title?'
    else:
        return title(field.replace('_', ' '))

def is_overdue(changeset):
    # do this correctly and with variables in settings if we ever do the 
    # enforcing of the reservation limit according to the vote
    if datetime.today() - changeset.created > timedelta(weeks=8):
        return mark_safe("class='overdue'")
    else:
        return ""

def link_other_reprint(reprint, is_source):
    if is_source:
        if hasattr(reprint, 'target'):
            text = '<a href="%s">%s</a> <br> of %s' % \
                     (reprint.target.get_absolute_url(),
                      show_story_short(reprint.target),
                      reprint.target.issue.full_name())
        else:
            text = '<a href="%s">%s</a>' % \
                     (reprint.target_issue.get_absolute_url(),
                      reprint.target_issue.full_name())
    else:
        if hasattr(reprint, 'origin'):
            text = '<a href="%s">%s</a> <br> of %s' % \
                     (reprint.origin.get_absolute_url(),
                      show_story_short(reprint.origin),
                      reprint.origin.issue.full_name())
        else:
            text = '<a href="%s">%s</a>' % \
                     (reprint.origin_issue.get_absolute_url(),
                      reprint.origin_issue.full_name())
    return mark_safe(text)

def key(d, key_name):
    try:
        value = d[key_name]
    except KeyError:
        from django.conf import settings

        value = settings.TEMPLATE_STRING_IF_INVALID

    return value

def str_encl(string, bracket):
    if string:
        if bracket == '(':
            return '(' + string + ')'
        elif bracket == '[':
            return '[' + string + ']'
        elif bracket == '{':
            return '{' + string + '}'
    return string

def object_filter(search_result):
    if hasattr(search_result, 'object'):
        return search_result.object
    else:
        return search_result

def current_search(selected, search):
    if selected:
        if search == selected:
            return mark_safe('"%s" selected' % search)
    else:
        if search == 'haystack':
            return mark_safe('"%s" selected' % search)
    return mark_safe('"%s"' % search)

register.filter(current_search)
register.filter(object_filter)
register.filter(str_encl)
register.filter(key)
register.filter(absolute_url)
register.filter(cover_image_tag)
register.filter(show_story_short)
register.filter(show_revision_short)
register.filter(show_volume)
register.filter(show_issue)
register.filter(show_series_tracking)
register.filter(show_indicia_pub)
register.filter(show_revision_type)
register.filter(header_link)
register.filter(changed_fields)
register.filter(changed_story_list)
register.filter(field_name)
register.filter(is_overdue)
register.filter(link_other_reprint)
