from django import template
from diff_match_patch import diff_match_patch
from django.conf import settings
from django.template.defaultfilters import yesno, linebreaksbr, urlize, \
                                           pluralize
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from stdnum import ean as stdean

from apps.gcd.templatetags.display import absolute_url, \
                                          sum_page_counts, show_barcode, \
                                          show_isbn
from apps.gcd.templatetags.credits import format_page_count, \
                                          split_reprint_string

from apps.oi import states
from apps.oi.models import remove_leading_article, validated_isbn, \
                           ReprintRevision, StoryRevision, IssueRevision
from apps.gcd.models import CREDIT_TYPES, VARIANT_COVER_STATUS
from apps.oi.templatetags.editing import is_locked

register = template.Library()


def valid_barcode(barcode):
    '''
    validates a barcode with stdnum
    '''

    # remove space and hyphens
    try:
        barcode = str(barcode).replace('-', '').replace(' ', '')
        int(barcode)
    except ValueError:
        return False

    if len(barcode) > 16:
        # if extra 5 digits remove them (EAN 5)
        barcode = barcode[:-5]
    elif len(barcode) > 13:
        # if extra 2 digits remove them (EAN 2)
        barcode = barcode[:-2]

    return stdean.is_valid(barcode)


# check to return True for yellow css compare highlighting
@register.filter
def check_changed(changed, field):
    if changed:
        return changed[field]
    return False


# display certain similar fields' data in the same way
@register.filter
def field_value(revision, field):
    value = getattr(revision, field)
    if field in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing']:
        value = esc(value)
        if type(revision).__name__ == 'IssueRevision':
            credits = revision.issue_credit_revisions.filter(
                credit_type__id=CREDIT_TYPES[field],
                deleted=False)
        else:
            credits = revision.story_credit_revisions.filter(
                               credit_type__id=CREDIT_TYPES[field],
                               deleted=False)
        if value and credits:
            value += '; '
        for credit in credits:
            value += credit.creator.display_credit(credit, url=True,
                                                   compare=True,
                                                   show_sources=True) + '; '
        if credits:
            value = value[:-2]
        return mark_safe(value)
    if field == 'characters':
        return mark_safe(revision.show_characters(css_style=False,
                                                  compare=True))
    if field in ['is_surrogate', 'no_volume', 'display_volume_with_number',
                 'no_brand', 'page_count_uncertain', 'title_inferred',
                 'no_barcode', 'no_indicia_frequency', 'no_isbn',
                 'year_began_uncertain', 'year_overall_began_uncertain',
                 'year_ended_uncertain', 'year_overall_ended_uncertain',
                 'on_sale_date_uncertain', 'is_comics_publication',
                 'no_indicia_printer', 'has_indicia_printer',
                 'has_about_comics' 'has_publisher_code_number']:
        return yesno(value, 'Yes,No')
    elif field in ['is_current']:
        res_holder_display = ''
        if revision.previous():
            reservation = revision.source.get_ongoing_reservation()
            if revision.previous().is_current and not value and reservation:
                res_holder = reservation.indexer
                res_holder_display = ' (ongoing reservation held by %s %s)' % \
                                     (res_holder.first_name,
                                      res_holder.last_name)
        return yesno(value, 'Yes,No') + res_holder_display
    elif field in ['publisher', 'indicia_publisher', 'series',
                   'origin_issue', 'target_issue', 'award',
                   'from_feature', 'to_feature', 'character',
                   'from_group', 'to_group', 'from_character', 'to_character']:
        return absolute_url(value)
    elif field in ['origin', 'target']:
        return value.full_name_with_link()
    elif field == 'brand':
        if value and value.emblem:
            if settings.FAKE_IMAGES:
                return absolute_url(value)
            else:
                return mark_safe('<img src="' + value.emblem.icon.url + '"> '
                                 + absolute_url(value))
        return absolute_url(value)
    elif field in ['feature_object', 'feature_logo']:
        first = True
        features = ''
        for feature in value.all():
            if first:
                first = False
            else:
                features += '; '
            if field == 'feature_object':
                features += '<a href="%s">%s</a>' % (
                  feature.get_absolute_url(),
                  esc(feature.name_with_disambiguation()))
            else:
                features += absolute_url(feature, feature.logo)
        return mark_safe(features)
    elif field in ['notes', 'tracking_notes', 'publication_notes',
                   'synopsis']:
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
        if revision.source_name == 'brand':
            brand_groups = ''
            for brand in value.all():
                brand_groups += absolute_url(brand) + '; '
            if brand_groups:
                brand_groups = brand_groups[:-2]
            return mark_safe(brand_groups)
        else:
            return absolute_url(value)
    elif field == 'indicia_printer':
        printers = ''
        for printer in value.all():
            printers += absolute_url(printer) + '; '
        if printers:
            printers = printers[:-2]
        return mark_safe(printers)
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

            return '%s (note: total sum of story page counts is %s)' % \
                   (format_page_count(value), sum_story_pages)
        return format_page_count(value)
    elif field == 'isbn':
        if value:
            if validated_isbn(value):
                return '%s (note: valid ISBN)' % show_isbn(value)
            elif len(value.split(';')) > 1:
                return_val = show_isbn(value) + ' (note: '
                for isbn in value.split(';'):
                    return_val = return_val + '%s; ' % (
                      "valid ISBN" if validated_isbn(isbn) else "invalid ISBN")
                return return_val + 'ISBNs are inequal)'
            elif value:
                return '%s (note: invalid ISBN)' % value
    elif field == 'barcode':
        if value:
            barcodes = value.split(';')
            return_val = show_barcode(value) + ' (note: '
            for barcode in barcodes:
                return_val = return_val + '%s; ' % (
                  "valid UPC/EAN part" if valid_barcode(barcode)
                  else "invalid UPC/EAN part or non-standard")
            return return_val[:-2] + ')'
    elif field == 'leading_article':
        if value is True:
            return 'Yes (sorted as: %s)' % remove_leading_article(
              revision.name)
        else:
            return 'No'
    elif field in ['has_barcode', 'has_isbn', 'has_issue_title',
                   'has_indicia_frequency', 'has_volume', 'has_rating']:
        if hasattr(revision, 'changed'):
            if revision.changed[field] and value is False:
                kwargs = {field[4:]: ''}
                if field[4:] == 'issue_title':
                    kwargs = {'title': ''}
                if revision.series:
                    value_count = revision.series.active_issues()\
                                                 .exclude(**kwargs).count()
                    if value_count:
                        return 'No (note: %d issues have a non-empty %s '\
                               'value)' % (value_count, field[4:])
        return yesno(value, 'Yes,No')
    elif field == 'is_singleton':
        if hasattr(revision, 'changed'):
            if revision.changed[field] and value is True:
                if revision.series:
                    value_count = revision.series.active_base_issues().count()
                    if value_count != 1:
                        return 'Yes (note: the series has %d issue%s)' % \
                               (value_count, pluralize(value_count))
                    elif revision.series.active_issues()\
                                 .exclude(indicia_frequency='').count():
                        return 'Yes (note: the issue has an indicia frequency)'
        return yesno(value, 'Yes,No')
    elif field == 'after' and not hasattr(revision, 'changed'):
        # for previous revision (no attr changed) display empty string
        return ''
    elif field == 'cr_creator_names':
        creator_names = ", ".join(value.all().values_list('name', flat=True))
        return creator_names
    elif field == 'creator_name':
        creator_names = "; ".join(value.all().values_list('name', flat=True))
        return creator_names
    elif field == 'feature_object':
        features = "; ".join(value.all().values_list('name', flat=True))
        return features
    elif field == 'feature_logo':
        features = "; ".join(value.all().values_list('name', flat=True))
        return features
    elif field == 'indicia_printer':
        features = "; ".join(value.all().values_list('name', flat=True))
        return features
    elif field == 'feature' and \
      revision._meta.model_name == 'featurelogorevision':
        features = ''
        for feature in value.all():
            features += absolute_url(feature) + '; '
        if features:
            features = features[:-2]
        return mark_safe(features)
    elif field == 'name' and \
      revision._meta.model_name == 'creatorsignaturerevision':
        if revision.source:
            return absolute_url(revision.source, descriptor=value)
    elif field == 'variant_cover_status':
        return VARIANT_COVER_STATUS[value]
    return value


@register.simple_tag
def diff_list(prev_rev, revision, field):
    """Generates an array which describes the change in text fields"""
    if field in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing',
                 'characters']:
        diff = diff_match_patch().diff_main(field_value(prev_rev, field),
                                            field_value(revision, field))
        diff_match_patch().diff_cleanupSemantic(diff)
        new_diff = []
        splitted_link = False
        splitted_signature_link = False
        for di in diff:
            if splitted_link or splitted_signature_link:
                if di[1].find('/">') >= 0 and di[0] != 0:
                    pos = di[1].find('/">') + len('/">')
                    if di[0] == 1:
                        di = (2, di[1][:pos] + "<span class='added'>"
                              + di[1][pos:])
                        splitted_link = False
                        splitted_signature_link = False
                    else:
                        di = (-2, di[1][:pos] + "<span class='deleted'>"
                              + di[1][pos:])
                elif di[1].find('/">') >= 0 and di[0] == 0:
                    splitted_link = False
                    splitted_signature_link = False
                else:
                    di = (3 * di[0], di[1])
            if di[1].find('<a href="/creator/') >= 0 and \
               di[1].find('/">', di[1].rfind('<a href="/creator/')) < 0:
                splitted_link = True
            elif di[1].find('<a href="/creator_signature/') >= 0 and \
              di[1].rfind('/">',
                          di[1].rfind('<a href="/creator_signature/')) < 0:
                splitted_signature_link = True
            elif di[1].find('<a href="/character/') >= 0 and \
              di[1].find('/">', di[1].rfind('<a href="/character/')) < 0:
                splitted_link = True
            new_diff.append((di[0], mark_safe(di[1])))
        return new_diff
    if field in ['notes', 'tracking_notes', 'publication_notes',
                 'synopsis', 'title', 'first_line',
                 'format', 'color', 'dimensions', 'paper_stock', 'binding',
                 'publishing_format', 'format', 'name',
                 'price', 'indicia_frequency', 'variant_name',
                 'source_description', 'gcd_official_name', 'bio']:
        diff = diff_match_patch().diff_main(getattr(prev_rev, field),
                                            getattr(revision, field))
        diff_match_patch().diff_cleanupSemantic(diff)
        return diff
    else:
        return None


@register.filter
def show_diff(diff_list, change):
    """show changes in diff with markings for add/delete"""
    compare_string = ""
    span_tag = "<span class='%s'>%s</span>"
    if change == "orig":
        for i in diff_list:
            if i[0] == 0:
                compare_string += esc(i[1])
            elif i[0] == -1:
                compare_string += span_tag % ("deleted", esc(i[1]))
            elif i[0] == -2:
                compare_string += esc(i[1]) + "</span>"
            elif i[0] == -3:
                compare_string += esc(i[1])
    else:
        for i in diff_list:
            if i[0] == 0:
                compare_string += esc(i[1])
            elif i[0] == 1:
                compare_string += span_tag % ("added", esc(i[1]))
            elif i[0] == 2:
                compare_string += esc(i[1]) + "</span>"
            elif i[0] == 3:
                compare_string += esc(i[1])
    return mark_safe(compare_string)


@register.filter
def compare_current_reprints(object_type, changeset):
    """process reprint_links and parse into readable format for compare view"""
    if object_type.changeset_id != changeset.id:
        if not object_type.source:
            return ''
        active = ReprintRevision.objects.filter(
          next_revision__in=changeset.reprintrevisions.all())
        if type(object_type) == StoryRevision:
            active_origin = active.filter(origin=object_type.source)
            active_target = active.filter(target=object_type.source)
        else:
            active_origin = active.filter(origin_issue=object_type.source,
                                          origin=None)
            active_target = active.filter(target_issue=object_type.source,
                                          target=None)
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
    if type(object_type) == IssueRevision:
        active_origin = active_origin.filter(origin=None, origin_revision=None)
        active_target = active_target.filter(target=None, target_revision=None)

    if not object_type.source:
        kept_origin = ReprintRevision.objects.none()
        kept_target = ReprintRevision.objects.none()
    else:
        kept_origin = object_type.source.origin_reprint_revisions\
          .filter(changeset__modified__lte=changeset.modified)\
          .exclude(changeset=changeset)\
          .filter(changeset__state=states.APPROVED)\
          .exclude(deleted=True)

        kept_target = object_type.source.target_reprint_revisions\
          .filter(changeset__modified__lte=changeset.modified)\
          .exclude(changeset=changeset)\
          .filter(changeset__state=states.APPROVED)\
          .exclude(deleted=True)
        if type(object_type) == IssueRevision:
            kept_origin = kept_origin.filter(origin=None, origin_revision=None)
            kept_target = kept_target.filter(target=None, target_revision=None)

    if active_origin.exists() or active_target.exists():
        if object_type.changeset_id != changeset.id:
            reprint_string = '<ul>The following reprint links are edited in ' \
                             'the compared changeset.'
        else:
            reprint_string = '<ul>The following reprint links are edited ' \
                             'in this changeset.'

        active_target = active_target.select_related(
                        'origin_issue__series__publisher',
                        'origin_revision__issue__series__publisher',
                        'target_issue',
                        'target_revision__issue')
        active_target = active_target.order_by('origin_issue__key_date')

        active_origin = active_origin.select_related(
                        'target_issue__series__publisher',
                        'target_revision__issue__series__publisher',
                        'origin_issue',
                        'origin_revision__issue')
        active_origin = active_origin.order_by('target_issue__key_date')

        for reprint in (active_origin | active_target):
            if object_type.changeset_id != changeset.id:
                do_compare = False
                action = ''
            else:
                do_compare = True
                if reprint.previous_revision is None:
                    action = " <span class='added'>[ADDED]</span>"
                elif reprint.deleted:
                    action = " <span class='deleted'>[DELETED]</span>"
                else:
                    action = ""
            reprint_string = '%s<li>%s%s</li>' % (
              reprint_string,
              reprint.get_compare_string(object_type.issue,
                                         do_compare=do_compare),
              action)
        reprint_string += '</ul>'
    else:
        reprint_string = ''

    if kept_origin.exists() or kept_target.exists():
        kept_string = ''
        kept_target = kept_target.order_by('origin_issue__key_date')
        kept_origin = kept_origin.order_by('target_issue__key_date')

        for reprint in kept_origin.union(kept_target):
            # the checks for nex_revision.changeset seemingly cannot be done
            # in the filter/exclude process above. next_revision does not need
            # to exists and makes problems in that.
            if not hasattr(reprint, 'next_revision') or \
              (reprint.next_revision.changeset != changeset and not
                (reprint.next_revision.changeset.state == states.APPROVED and
                 reprint.next_revision.changeset.modified <= changeset.modified)):
                kept_string = '%s<li>%s' % (
                  kept_string, reprint.get_compare_string(object_type.issue))
                if reprint.source and is_locked(reprint.source):
                    kept_string += '<br>reserved in a different changeset'
                kept_string += '</li>'
        if kept_string != '':
            reprint_string += '</ul>The following reprint links are not ' \
                'part of this change.<ul>' + kept_string

    return mark_safe(reprint_string)


@register.filter
def show_credit_status(story):
    """
    Display a set of letters indicating which of the required credit fields
    have been filled out.  Technically, the editing field is not required but
    it has historically been displayed as well.  The required editing field
    is now directly on the issue record.
    """
    status = []
    required_remaining = 5

    if story.script or story.no_script or \
       story.story_credit_revisions.filter(credit_type__name='script')\
                                   .exists():
        status.append('S')
        required_remaining -= 1

    if story.pencils or story.no_pencils or \
       story.story_credit_revisions.filter(credit_type__name='pencils')\
                                   .exists():
        status.append('P')
        required_remaining -= 1

    if story.inks or story.no_inks or \
       story.story_credit_revisions.filter(credit_type__name='inks')\
                                   .exists():
        status.append('I')
        required_remaining -= 1

    if story.colors or story.no_colors or \
       story.story_credit_revisions.filter(credit_type__name='colors')\
                                   .exists():
        status.append('C')
        required_remaining -= 1

    if story.letters or story.no_letters or \
       story.story_credit_revisions.filter(credit_type__name='letters')\
                                   .exists():
        status.append('L')
        required_remaining -= 1

    if story.editing or story.no_editing or \
       story.story_credit_revisions.filter(credit_type__name='editing')\
                                   .exists():
        status.append('E')

    completion = 'complete'
    if required_remaining:
        completion = 'incomplete'
    snippet = '[<span class="%s">' % completion
    snippet += ' '.join(status)
    snippet += '</span>]'
    return mark_safe(snippet)


@register.filter
def get_source_revisions(changeset, field):
    revisions = changeset.datasourcerevisions.filter(field=field)
    for revision in revisions:
        revision.compare_changes()
    return revisions


@register.filter
def lookup(d, key):
    return d[key]


@register.filter
def is_in(value, sources):
    for source in sources:
        if str(source) == str(value):
            return True
    return False


@register.filter
def is_equal(value, relation_obj):
    for relation in relation_obj:
        if relation.rel_type:
            if str(relation.rel_type.type) == str(value):
                return True
    return False


@register.filter
def relation_source_is_in(value, relation_objs):
    for relation_obj in relation_objs:
        for source in relation_obj.rel_source.all():
            if str(source.type) == str(value):
                return True
    return False
