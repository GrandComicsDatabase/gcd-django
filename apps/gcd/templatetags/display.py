from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template
from django.template.defaultfilters import yesno, linebreaksbr, title, urlize

from apps.oi.models import StoryRevision, CTYPES
from apps.gcd.templatetags.credits import show_page_count, format_page_count, sum_page_counts
import datetime

NEW_SITE_CREATION_DATE = datetime.date(2009, 12, 1)

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

        # get first skeleton's display num
        revision = changeset.issuerevisions.order_by('revision_sort_code')[0]
        issue_num = revision.display_number
        if revision.issue:
            # if it's been approved, make it a link to real issue
            issue_num = u'<a href="%s">%s</a>' % (revision.issue.get_absolute_url(), issue_num)

        if changeset.issuerevisions.count() > 1:
            # if it was a bulk skeleton, do same for last issue number
            last_revision = changeset.issuerevisions.order_by('-revision_sort_code')[0]
            last_issue_num = last_revision.display_number
            if last_revision.issue:
                last_issue_num = u'<a href="%s">%s</a>' % (last_revision.issue.get_absolute_url(), last_issue_num)
            issue_num = u'%s - %s' % (issue_num, last_issue_num)

        return mark_safe(u'%s (%s) %s' % (series_url, pub_url, issue_num))
    else:
        return u''

# get a human readable list of fields changed in a given approved changeset
def changed_fields(changeset, object_id):
    if changeset.inline():
        revision = changeset.inline_revision()
    elif changeset.issuerevisions.count() == 1:
        revision = changeset.issuerevisions.all()[0]
    else:
        revision = changeset.issuerevisions.all().get(issue=object_id)

    prev_rev = revision.previous()
    changed_list = []
    if prev_rev is None:
        # there was no previous revision so only list the initial add of the object.
        # otherwise too many fields to list.
        # note that if an object predates the server move, the first revision right
        # now is not the initial add (but it doesn't harm to show it as such atm).
        # when the old log tables are migrated, it will be more accurate.
        if revision.source.created.date() > NEW_SITE_CREATION_DATE:
            changed_list = [u'%s added' % title(revision.source_name.replace('_', ' '))]
        else:
            changed_list = [u'First change to %s on new site. Older change \
                            history coming soon.' % revision.source_name.replace('_', ' ')]
    elif revision.deleted:
        changed_list = [u'%s deleted' % title(revision.source_name.replace('_', ' '))]
    else:
        for field in revision._field_list():
            if field == 'after':
                # most ignorable fields handled in oi/view.py/compare()
                # but this one should also be ignored on the initial change
                # history page. the only time it's relevant the line will
                # read "issue added"
                continue
            if getattr(revision, field) != getattr(prev_rev, field):
                changed_list.append(field_name(field))
    return ", ".join(changed_list)

# get a bulleted list of changes at the sequence level
def changed_story_list(changeset):
    if changeset.issuerevisions.count() == 1:
        # only relevant for single issue changesets
        story_revisions = changeset.storyrevisions.all().order_by('sequence_number')
    else:
        return u''

    # don't display sequence level breakdown if this is first change for an
    # object that predates the new site.
    issue_rev = changeset.issuerevisions.all()[0]
    prev_issue_rev = issue_rev.previous()
    if prev_issue_rev is None and issue_rev.source.created.date() < NEW_SITE_CREATION_DATE:
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
                    if getattr(story_revision, field) != getattr(prev_story_rev, field):
                        story_changed_list.append(field_name(field))
            if story_changed_list:
                output += u'<li>Sequence %s : %s' % (story_revision.sequence_number, ", ".join(story_changed_list))
        if output is not u'':
            output = u'<ul>%s</ul>' % output
    return mark_safe(output)

# check to return True for yellow css compare highlighting 
def check_changed(changed, field):
    if changed:
        return changed[field]
    return False

# display certain similar fields' data in the same way
def field_value(revision, field):
    value = getattr(revision, field)
    if field in ['is_current', 'is_surrogate', 'no_volume',
                 'display_volume_with_number', 'no_brand',
                 'page_count_uncertain', 'title_inferred']:
        return yesno(value, 'Yes,No')
    elif field in ['publisher', 'indicia_publisher', 'brand']:
        return absolute_url(value)
    elif field in ['notes', 'tracking_notes', 'publication_notes',
                   'characters', 'synopsis', 'reprint_notes']:
        return linebreaksbr(value)
    elif field in ['url']:
        return urlize(value)
    elif field in ['indicia_pub_not_printed']:
        return yesno(value, 'Not Printed,Printed')
    elif field in ['no_editing', 'no_script', 'no_pencils', 'no_inks',
                   'no_colors', 'no_letters']:
        return yesno(value, 'X, ')
    elif field in ['page_count']:
        if revision.source_name == 'issue' and revision.changeset.storyrevisions.count():
            # only calculate total sum for issue not sequences
            sum_story_pages = format_page_count(sum_page_counts(
                              revision.changeset.storyrevisions.all()))
            return u'%s (total sum of story page counts: %s)' % \
                   (format_page_count(value), sum_story_pages)
        return format_page_count(value)
    return value

# translate field name into more human friendly name
def field_name(field):
    if field in ['name', 'publisher', 'country', 'language', 'notes', 'format',
                 'imprint', 'number', 'volume', 'brand', 'editing', 'type',
                 'title', 'feature', 'genre', 'script', 'pencils', 'inks',
                 'colors', 'letters', 'characters', 'synopsis', 'price']:
        return title(field)
    elif field in ['year_began', 'year_ended', 'tracking_notes', 'publication_notes',
                   'no_volume', 'display_volume_with_number', 'publication_date',
                   'indicia_frequency', 'key_date', 'indicia_publisher',
                   'no_brand', 'page_count', 'page_count_uncertain', 'no_editing',
                   'sequence_number', 'no_script', 'no_pencils', 'no_inks',
                   'no_colors', 'no_letters', 'job_number', 'reprint_notes']:
        return title(field.replace('_', ' '))
    elif field in ['is_current', 'is_surrogate']:
        return u'%s?' % title(field.replace(u'is_', u''))
    elif field == 'url':
        return field.upper()
    elif field == 'after':
        return u'Add Issue After'
    elif field == 'indicia_pub_not_printed':
        return u'Indicia Publisher Not Printed'
    elif field == 'title_inferred':
        return u'Unofficial Title?'
    return u''

register.filter(absolute_url)
register.filter(show_story_short)
register.filter(show_revision_short)
register.filter(show_volume)
register.filter(show_issue)
register.filter(show_indicia_pub)
register.filter(show_revision_type)
register.filter(header_link)
register.filter(changed_fields)
register.filter(changed_story_list)
register.filter(check_changed)
register.filter(field_value)
register.filter(field_name)
