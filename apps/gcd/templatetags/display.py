from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template

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
            title = u'[%s]' % story.title
        else:
            title = story.title
    else:
        title = '<span class="no_data">no title</span>'
    if story.feature:
        story_line = u'%s %s (%s)' % (esc(story_line), title, 
                                      esc(story.feature))
    else:
        story_line = u'%s %s (%s)' % (esc(story_line), title, 
                                     '<span class="no_data">no feature</span>')
    story_line = u'%s %s, %sp' % (story_line, story.type, 
                                  show_page_count(story))
    return mark_safe(story_line)

def show_issue(issue):
    return mark_safe('<a href="%s">%s</a> (%s series) <a href="%s">#%s</a>' %
                     (issue.series.get_absolute_url(),
                      esc(issue.series.name),
                      esc(issue.series.year_began),
                      issue.get_absolute_url(),
                      esc(issue.display_number)))

register.filter(absolute_url)
register.filter(show_story_short)
register.filter(show_issue)

