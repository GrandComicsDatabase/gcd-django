from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template

from apps.oi.models import StoryRevision, CTYPES
from apps.gcd.templatetags.credits import show_page_count

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

def show_story_short(story):
    story_line = u'%s.' % story.sequence_number
    if story.title:
        if story.title_inferred:
            title = u'[%s]' % esc(story.title)
        else:
            title = esc(story.title)
    else:
        title = '<span class="no_data">no title</span>'
    if story.feature:
        story_line = u'%s %s (%s)' % (esc(story_line), title, 
                                      esc(story.feature))
    else:
        story_line = u'%s %s (%s)' % (esc(story_line), title, 
                                     '<span class="no_data">no feature</span>')
    story_line = u'%s %s' % (story_line, story.type)
    page_count = show_page_count(story)
    if page_count:
        story_line += ', %sp' % page_count
    else:
        story_line += '<span class="no_data"> no page count</span>'

    return mark_safe(story_line)

def show_revision_short(revision):
    if revision is None:
        return u''
    if isinstance(revision, StoryRevision):
        return show_story_short(revision)
    return unicode(revision)

def show_volume(issue):
    if issue.no_volume:
        return u''
    if issue.volume is None:
        return u'?'
    return issue.volume

def show_issue(issue):
    return mark_safe('<a href="%s">%s</a> (%s series) <a href="%s">#%s</a>' %
                     (issue.series.get_absolute_url(),
                      esc(issue.series.name),
                      esc(issue.series.year_began),
                      issue.get_absolute_url(),
                      esc(issue.display_number)))

def show_indicia_pub(issue):
    if issue.indicia_publisher is None:
        if issue.indicia_pub_not_printed:
            ip_url = u'[none printed]'
        else:
            ip_url = u'?'
    else:
        ip_url = u'<a href=\"%s\">%s</a>' % (issue.indicia_publisher.get_absolute_url(), issue.indicia_publisher)
        if issue.indicia_pub_not_printed:
            ip_url += u' [not printed on item]'
    return mark_safe(ip_url)

def show_revision_type(cover):
    if cover.deleted:
        return u'[DELETED]'
    if cover.cover:
        return u'[REPLACEMENT]'
    if cover.issue.has_covers():
        return u'[VARIANT]'
    return u'[ADDED]'

def header_link(changeset):
    if changeset.inline():
        revision = changeset.inline_revision()
    else:
        revision = changeset.issuerevisions.all()[0]

    if changeset.change_type == CTYPES['publisher']:
        return absolute_url(revision)
    elif changeset.change_type == CTYPES['brand'] or \
         changeset.change_type == CTYPES['indicia_publisher']:
        return mark_safe(u'%s : %s' % (absolute_url(revision.parent), absolute_url(revision)))
    elif changeset.change_type == CTYPES['series']:
        return mark_safe(u'%s (%s)' % (absolute_url(revision), absolute_url(revision.publisher)))
    elif changeset.change_type == CTYPES['cover'] or \
         changeset.change_type == CTYPES['issue']:
        series_url = absolute_url(revision.issue.series)
        pub_url = absolute_url(revision.issue.series.publisher)
        issue_url = revision.issue.get_absolute_url()
        issue_num = revision.issue.display_number
        return mark_safe(u'%s (%s) <a href="%s">#%s</a>' % (series_url, pub_url, issue_url, issue_num))
    elif changeset.change_type == CTYPES['issue_add']:
        series_url = absolute_url(revision.series)
        pub_url = absolute_url(revision.series.publisher)
        display_num = changeset.issuerevisions.order_by('revision_sort_code')[0].display_number
        if changeset.issuerevisions.count() > 1:
            display_num = u'%s - %s' % (display_num,
              changeset.issuerevisions.order_by('-revision_sort_code')[0].display_number)
        return mark_safe(u'%s (%s) #%s' % (series_url, pub_url, display_num))
    else:
        return u''

register.filter(absolute_url)
register.filter(show_story_short)
register.filter(show_revision_short)
register.filter(show_volume)
register.filter(show_issue)
register.filter(show_indicia_pub)
register.filter(show_revision_type)
register.filter(header_link)
