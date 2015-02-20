from django import template
from diff_match_patch import diff_match_patch
from django.template.defaultfilters import yesno, linebreaksbr, urlize
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.templatetags.display import absolute_url, field_name, sum_page_counts
from apps.gcd.templatetags.credits import format_page_count, split_reprint_string

from apps.oi import states
from apps.oi.models import remove_leading_article, validated_isbn, \
                           ReprintRevision, StoryRevision

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
    try:
        barcode = str(barcode).replace('-', '').replace(' ', '')
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

# check to return True for yellow css compare highlighting
def check_changed(changed, field):
    if changed:
        return changed[field]
    return False

# display certain similar fields' data in the same way
def field_value(revision, field):
    value = getattr(revision, field)
    if field in ['is_surrogate', 'no_volume', 'display_volume_with_number',
                 'no_brand', 'page_count_uncertain', 'title_inferred',
                 'no_barcode', 'no_indicia_frequency', 'no_isbn',
                 'year_began_uncertain', 'year_ended_uncertain',
                 'on_sale_date_uncertain', 'is_comics_publication']:
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
    elif field in ['publisher', 'indicia_publisher', 'series']:
        return absolute_url(value)
    elif field == 'brand':
        if value and value.emblem:
            return mark_safe('<img src="' + value.emblem.icon.url + '"> ' \
                             + absolute_url(value))
        return absolute_url(value)
    elif field in ['notes', 'tracking_notes', 'publication_notes',
                   'characters', 'synopsis']:
        return linebreaksbr(value)
    elif field == 'reprint_notes':
        reprint = ''
        if value.strip() != '':
            for string in split_reprint_string(value):
                string = string.strip()
                reprint += '<li> ' + esc(string) + ' </li>'
            if reprint != '':
                reprint = '<ul>' + reprint + '</ul>'
        return mark_safe(reprint)
    elif field in ['url']:
        return urlize(value)
    elif field in ['indicia_pub_not_printed']:
        return yesno(value, 'Not Printed,Printed')
    elif field == 'group':
        brand_groups = ''
        for brand in value.all():
            brand_groups += absolute_url(brand) + '; '
        if brand_groups:
            brand_groups = brand_groups[:-2]
        return mark_safe(brand_groups)
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
                return_val = value + ' (note: '
                for isbn in value.split(';'):
                    return_val = return_val + u'%s; ' % ("valid ISBN" \
                                   if validated_isbn(isbn) else "invalid ISBN")
                return return_val + 'ISBNs are inequal)'
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
                   'has_indicia_frequency', 'has_volume', 'has_rating']:
        if hasattr(revision, 'changed'):
            if revision.changed[field] and value == False:
                kwargs = {field[4:]: ''}
                if field[4:] == 'issue_title':
                    kwargs = {'title': ''}
                if revision.series:
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

@register.assignment_tag
def diff_list(prev_rev, revision, field):
    """Generates an array which describes the change in text fields"""
    if field in ['notes', 'tracking_notes', 'publication_notes',
                 'characters', 'synopsis', 'script', 'pencils', 'inks',
                 'colors', 'letters', 'editing', 'feature', 'title',
                 'format', 'color', 'dimensions', 'paper_stock', 'binding',
                 'publishing_format', 'format', 'name', 
                 'price', 'indicia_frequency']:
        diff = diff_match_patch().diff_main(getattr(prev_rev, field),
                                            getattr(revision, field))
        diff_match_patch().diff_cleanupSemantic(diff)
        return diff
    else:
        return None

def show_diff(diff_list, change):
    """show changes in diff with markings for add/delete"""
    compare_string = u""
    span_tag = "<span class='%s'>%s</span>"
    if change == "orig":
        for i in diff_list:
            if i[0] == 0:
                compare_string += esc(i[1])
            elif i[0] == -1:
                compare_string += span_tag % ("deleted", esc(i[1]))
    else:
        for i in diff_list:
            if i[0] == 0:
                compare_string += esc(i[1])
            elif i[0] == 1:
                compare_string += span_tag % ("added", esc(i[1]))
    return mark_safe(compare_string)

def compare_current_reprints(object_type, changeset):
    """process reprint_links and parse into readable format for compare view"""
    if object_type.changeset_id != changeset.id:
        if not object_type.source:
            return ''
        active = ReprintRevision.objects.filter(next_revision__in= \
                                         changeset.reprintrevisions.all())
        if type(object_type) == StoryRevision:
            active_origin = active.filter(origin_story=object_type.source)
            active_target = active.filter(target_story=object_type.source)
        else:
            active_origin = active.filter(origin_issue=object_type.source)
            active_target = active.filter(target_issue=object_type.source)
    else:
        if not object_type.source:
            active_origin = object_type.origin_reprint_revisions\
                                       .filter(changeset=changeset)
            active_target = object_type.target_reprint_revisions\
                                       .filter(changeset=changeset)
        else:
            active_origin = object_type.source.origin_reprint_revisions\
                .filter(changeset=changeset)
            active_target = object_type.source.target_reprint_revisions\
                .filter(changeset=changeset)

    if not object_type.source:
        kept_origin = ReprintRevision.objects.none()
        kept_target = ReprintRevision.objects.none()
    else:
        kept_origin = object_type.source.origin_reprint_revisions\
          .filter(changeset__modified__lte=changeset.modified)\
          .filter(next_revision=None).exclude(changeset=changeset)\
          .filter(changeset__state=states.APPROVED)\
          .exclude(deleted=True)
        kept_origin = kept_origin | object_type.source.origin_reprint_revisions\
          .filter(changeset__modified__lte=changeset.modified)\
          .exclude(changeset=changeset).filter(changeset__state=states.APPROVED)\
          .exclude(deleted=True).exclude(next_revision=None)

        kept_target = object_type.source.target_reprint_revisions\
          .filter(changeset__modified__lte=changeset.modified)\
          .filter(next_revision=None).exclude(changeset=changeset)\
          .filter(changeset__state=states.APPROVED)\
          .exclude(deleted=True)
        kept_target = kept_target | object_type.source.target_reprint_revisions\
          .filter(changeset__modified__lte=changeset.modified)\
          .exclude(changeset=changeset).filter(changeset__state=states.APPROVED)\
          .exclude(deleted=True).exclude(next_revision=None)

    if (active_origin | active_target).count():
        if object_type.changeset_id != changeset.id:
            reprint_string = '<ul>The following reprint links are edited in ' \
                             'the compared changeset.'
        else:
            reprint_string = '<ul>The following reprint links are edited ' \
                             'in this changeset.'

        active_target = list(active_target.select_related(\
                             'origin_issue__series__publisher',
                             'origin_story__issue__series__publisher',
                             'origin_revision__issue__series__publisher',
                             'target_issue',
                             'target_story__issue',
                             'target_revision__issue'))
        active_target = sorted(active_target, key=lambda a: a.origin_sort)

        active_origin = list(active_origin.select_related(\
                            'target_issue__series__publisher',
                            'target_story__issue__series__publisher',
                            'target_revision__issue__series__publisher',
                            'origin_issue',
                            'origin_story__issue',
                            'origin_revision__issue'))
        active_origin = sorted(active_origin, key=lambda a: a.target_sort)

        for reprint in active_target + active_origin:
            if object_type.changeset_id != changeset.id:
                do_compare = False
                action = ''
            else:
                do_compare = True
                if reprint.in_type == None:
                    action = " <span class='added'>[ADDED]</span>"
                elif reprint.deleted:
                    action = " <span class='deleted'>[DELETED]</span>"
                else:
                    action = ""
            reprint_string = '%s<li>%s%s</li>' % (reprint_string,
              reprint.get_compare_string(object_type.issue,
                                         do_compare=do_compare),
              action)
        reprint_string += '</ul>'
    else:
        reprint_string = ''

    if (kept_origin | kept_target).count():
        kept_string = ''
        kept_target = list(kept_target.select_related(\
                           'origin_issue__series__publisher',
                           'origin_story__issue__series__publisher',
                           'origin_revision__issue__series__publisher',
                           'target_issue',
                           'target_story__issue',
                           'target_revision__issue'))
        kept_target = sorted(kept_target, key=lambda a: a.origin_sort)

        kept_origin = list(kept_origin.select_related(\
                           'target_issue__series__publisher',
                           'target_story__issue__series__publisher',
                           'target_revision__issue__series__publisher',
                           'origin_issue',
                           'origin_story__issue',
                           'origin_revision__issue'))
        kept_origin = sorted(kept_origin, key=lambda a: a.target_sort)

        for reprint in kept_target + kept_origin:
            # the checks for nex_revision.changeset seemingly cannot be done
            # in the filter/exclude process above. next_revision does not need
            # to exists and makes problems in that.
            if not hasattr(reprint, 'next_revision') or \
              ( reprint.next_revision.changeset != changeset and not
                ( reprint.next_revision.changeset.state == states.APPROVED and
                  reprint.next_revision.changeset.modified <= changeset.modified)):
                kept_string = '%s<li>%s' % (kept_string,
                  reprint.get_compare_string(object_type.issue))
                if reprint.source and reprint.source.reserved:
                    kept_string += '<br>reserved in a different changeset'
                kept_string += '</li>'
        if kept_string != '':
            reprint_string += '</ul>The following reprint links are not ' \
                'part of this change.<ul>' + kept_string

    return mark_safe(reprint_string)

register.filter(check_changed)
register.filter(field_value)
register.filter(show_diff)
register.filter(compare_current_reprints)
register.assignment_tag(diff_list)
