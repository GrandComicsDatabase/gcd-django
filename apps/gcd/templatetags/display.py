# -*- coding: utf-8 -*-
from decimal import Decimal

from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template
from django.template.defaultfilters import yesno, linebreaksbr, title, urlize

from apps.oi.models import StoryRevision, CTYPES, validated_isbn, \
                           remove_leading_article
from apps.gcd.templatetags.credits import show_page_count, format_page_count
from apps.gcd.models.publisher import IndiciaPublisher, Brand, Publisher
from apps.gcd.models.series import Series
from apps.gcd.models.issue import Issue
from apps.gcd.views.covers import get_image_tag

register = template.Library()

def valid_barcode(barcode):
    '''
    validates a barcode
    - ignore the check digit
    - count from right to left
    - add odd numbered times 3
    - add even numbered
    - 10 - (result modulo 10) is check digit
    - check digit of 10 becomes 0
    '''

    # remove space and hyphens
    barcode = str(barcode).replace('-', '').replace(' ', '')
    try:
        int(barcode)
    except ValueError:
        return False

    # if extra 5 digits remove them (EAN 5)
    if len(barcode) > 16:
        barcode = barcode[:-5]
    elif len(barcode) > 13:
        # if extra 2 digits remove them (EAN 2)
        barcode = barcode[:-2]

    if len(barcode) not in (13, 12, 8):
        return False

    odd = True
    check_sum = 0
    # odd/even from back
    for number in barcode[:-1][::-1]:
        if odd:
            check_sum += int(number)*3
        else:
            check_sum += int(number)
        odd = not odd

    check_digit = 10 - (check_sum % 10)
    if check_digit == 10:
        check_digit = 0
    if int(barcode[-1]) == check_digit:
        return True
    else:
        return False

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

def show_story_short(story, no_number=False):
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
    if issue.volume == '':
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
        revision = changeset.issuerevisions.all()[0]

    if changeset.change_type == CTYPES['publisher']:
        return absolute_url(revision)
    elif changeset.change_type == CTYPES['brand'] or \
         changeset.change_type == CTYPES['indicia_publisher']:
        return mark_safe(u'%s : %s' %
                         (absolute_url(revision.parent), absolute_url(revision)))
    elif changeset.change_type == CTYPES['series']:
        if revision.series and revision.publisher != revision.series.publisher:
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
    elif object_class is Publisher:
        revision = changeset.publisherrevisions.all().get(publisher=object.id)
    elif object_class is Brand:
        revision = changeset.brandrevisions.all().get(brand=object.id)
    elif object_class is IndiciaPublisher:
        revision = changeset.indiciapublisherrevisions.all()\
                            .get(indicia_publisher=object.id)

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
    if changeset.issuerevisions.count() == 1:
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

# check to return True for yellow css compare highlighting
def check_changed(changed, field):
    if changed:
        return changed[field]
    return False

def sum_page_counts(stories):
    """
    Return the sum of the story page counts.
    """
    count = Decimal(0)
    for story in stories:
        if story.page_count and not story.deleted:
            count += story.page_count
    return count

# display certain similar fields' data in the same way
def field_value(revision, field):
    value = getattr(revision, field)
    if field in ['is_surrogate', 'no_volume', 'display_volume_with_number',
                 'no_brand', 'page_count_uncertain', 'title_inferred',
                 'no_barcode', 'no_indicia_frequency', 'no_isbn',
                 'year_began_uncertain', 'year_ended_uncertain']:
        return yesno(value, 'Yes,No')
    elif field in ['is_current']:
        res_holder_display = ''
        if revision.previous():
            reservation = revision.source.get_ongoing_reservation()
            if revision.previous().is_current and not value and reservation:
                res_holder = reservation.indexer
                res_holder_display = ' (ongoing reservation held by %s %s)' % \
                  (res_holder.first_name, res_holder.last_name)
        return yesno(value, 'Yes,No') + res_holder_display
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
        if revision.source_name == 'issue' and \
           revision.changeset.storyrevisions.count():
            # only calculate total sum for issue not sequences
            total_pages = sum_page_counts(revision.active_stories())
            if revision.variant_of:
                if revision.changeset.issuerevisions.count() > 1:
                    stories = revision.changeset.storyrevisions\
                                      .exclude(issue=revision.issue)
                else:
                    stories = revision.variant_of.active_stories()
                if revision.active_stories().count():
                    # variant has cover sequence, add page counts without cover
                    stories = stories.exclude(sequence_number=0)
                    total_pages += sum_page_counts(stories)
                else:
                    # variant has no extra cover sequence
                    total_pages = sum_page_counts(stories)
            sum_story_pages = format_page_count(total_pages)

            return u'%s (note: total sum of story page counts is %s)' % \
                   (format_page_count(value), sum_story_pages)
        return format_page_count(value)
    elif field == 'isbn':
        if value:
            if validated_isbn(value):
                return u'%s (note: valid ISBN)' % value
            elif len(value.split(';')) > 1:
                return u'%s (note: invalid or inequal ISBNs)' % value
            elif value:
                return u'%s (note: invalid ISBN)' % value
    elif field == 'barcode':
        if value:
            barcodes = value.split(';')
            return_val = value + ' (note: '
            for barcode in barcodes:
                return_val = return_val + u'%s; ' % ("valid UPC/EAN" \
                             if valid_barcode(barcode) \
                             else "invalid UPC/EAN or non-standard")
            return return_val[:-2] + ')'
    elif field == 'leading_article':
        if value == True:
            return u'Yes (sorted as: %s)' % remove_leading_article(revision.name)
        else:
            return u'No'
    elif field in ['has_barcode', 'has_isbn', 'has_issue_title',
                   'has_indicia_frequency', 'has_volume']:
        if hasattr(revision, 'changed'):
            if revision.changed[field] and value == False:
                kwargs = {field[4:]: ''}
                value_count = revision.series.active_issues()\
                                            .exclude(**kwargs).count()
                if value_count:
                    return 'No (note: %d issues have a non-empty %s value)' % \
                            (value_count, field[4:])
        return yesno(value, 'Yes,No')
    elif field == 'after' and not hasattr(revision, 'changed'):
        # for previous revision (no attr changed) display empty string
        return ''
    return value

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

register.filter(absolute_url)
register.filter(cover_image_tag)
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
