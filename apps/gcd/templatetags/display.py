# -*- coding: utf-8 -*-
from decimal import Decimal
from stdnum import ean as stdean
from stdnum import isbn as stdisbn

from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template
from django.template.defaultfilters import title

from apps.oi import states
from apps.oi.models import StoryRevision, CTYPES, INDEXED
from apps.gcd.templatetags.credits import show_page_count, show_title
from apps.gcd.models import Creator, CreatorMembership, ReceivedAward, \
                                    CreatorArtInfluence, CreatorNonComicWork, \
                                    CreatorDegree, Award
from apps.gcd.models import IndiciaPublisher, Brand, BrandGroup, \
                                      Publisher
from apps.gcd.models import Series
from apps.gcd.models import Issue
from apps.gcd.models import Cover
from apps.gcd.models import Image
from apps.gcd.models.seriesbond import SeriesBond, BOND_TRACKING, \
                                       SUBNUMBER_TRACKING, MERGE_TRACKING
from apps.gcd.views.covers import get_image_tag

register = template.Library()

STATE_CSS_NAME = {
    states.UNRESERVED: 'available',
    states.BASELINE: 'baseline',
    states.OPEN: 'editing',
    states.PENDING: 'pending',
    states.DISCUSSED: 'discussed',
    states.REVIEWING: 'reviewing',
    states.APPROVED: 'approved',
    states.DISCARDED: 'discarded',
}


@register.filter
def absolute_url(item, additional=''):
    if item is not None and hasattr(item, 'get_absolute_url'):
        if additional:
            return mark_safe(u'<a href="%s" %s>%s</a>' %
                             (item.get_absolute_url(), additional, esc(item)))
        else:
            return mark_safe(u'<a href="%s">%s</a>' %
                             (item.get_absolute_url(), esc(item)))
    return ''


@register.filter
def cover_image_tag(cover, size_alt_text):
    size, alt_text = size_alt_text.split(',')
    return get_image_tag(cover, alt_text, int(size))


@register.filter
def show_story_short(story, no_number=False, markup=True):
    if no_number:
        story_line = u''
    else:
        story_line = u'%s.' % story.sequence_number

    if story.title or story.first_line:
        title = show_title(story, True)
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
            story_line = u'%s %s (%s)' % (
              esc(story_line),
              title,
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


@register.filter
def show_revision_short(revision, markup=True):
    if revision is None:
        return u''
    if isinstance(revision, StoryRevision):
        return show_story_short(revision, markup=markup)
    return unicode(revision)


@register.filter
def show_volume(issue):
    if issue.no_volume:
        return u''
    if issue.volume == '':
        return u'?'
    if issue.volume_not_printed:
        return u'[%s]' % issue.volume
    return issue.volume


@register.filter
def show_issue_number(issue_number):
    """
    Return issue number.
    """
    return mark_safe('<span class="issue_number">' + esc(issue_number)
                     + '</span>')


def show_one_barcode(_barcode):
    """
    display barcode, if two parts display separated.
    """

    # remove space and hyphens
    try:
        barcode = str(_barcode).replace('-', '').replace(' ', '')
        int(barcode)
    except ValueError:
        return _barcode

    if len(barcode) > 16:
        # if extra 5 digits remove them (EAN 5)
        first = barcode[:-5]
        if stdean.is_valid(first):
            return '%s %s' % (first, barcode[-5:])
    elif len(barcode) > 13:
        # if extra 2 digits remove them (EAN 2)
        first = barcode[:-2]
        if stdean.is_valid(first):
            return '%s %s' % (first, barcode[-2:])

    return barcode


@register.filter
def show_barcode(_barcode):
    barcode = ''
    for code in _barcode.split(';'):
        barcode += show_one_barcode(code) + '; '
    if barcode:
        # chop trailing '; '
        return barcode[:-2]


@register.filter
def show_isbn(_isbn):
    isbn = ''
    for code in _isbn.split(';'):
        if stdisbn.is_valid(code):
            isbn += stdisbn.format(code) + '; '
        else:
            isbn += code + '; '
    if isbn:
        # chop trailing '; '
        return isbn[:-2]


@register.filter
def show_issue(issue):
    if issue.display_number:
        issue_number = '%s' % (esc(issue.display_number))
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


@register.filter
def show_series_tracking(series):
    tracking_line = u""
    if not series.has_series_bonds():
        return mark_safe(tracking_line)

    srbonds = series.series_relative_bonds(bond_type__id__in=BOND_TRACKING)
    srbonds.sort()

    # See if we have any notes between links, because we'll format differently
    # for that.  However, if only the last link has a note, we don't care
    # because there's no following note for it to crowd up against.
    has_interior_notes = False
    for srbond in srbonds[0:-1]:
        if srbond.bond.notes:
            has_interior_notes = True
            break

    for srbond in srbonds:
        if series == srbond.bond.target:
            near_issue_preposition = u"with"
            far_issue_preposition = u"from"
            far_preposition = u"from"
        elif series == srbond.bond.origin:
            near_issue_preposition = u"after"
            far_issue_preposition = u"with"
            far_preposition = u"in"
            if srbond.bond.bond_type.id in MERGE_TRACKING:
                far_issue_preposition = u"into"
                far_preposition = u"into"
        else:
            # Wait, why are we here?  Should we assert on this?
            continue

        if srbond.bond.bond_type.id == SUBNUMBER_TRACKING:
            tracking_line += '<li> subnumbering continues '
        elif srbond.bond.bond_type.id in MERGE_TRACKING:
            tracking_line += '<li> merged '
        else:
            tracking_line += '<li> numbering continues '
        if (srbond.near_issue != srbond.near_issue_default):
            tracking_line += '%s %s ' % (
                near_issue_preposition, srbond.near_issue.display_number)
        if srbond.has_explicit_far_issue:
            tracking_line += '%s %s' % (
                far_issue_preposition, srbond.far_issue.full_name_with_link())
        else:
            tracking_line += '%s %s' % (
                far_preposition, srbond.far_series.full_name_with_link())

        if srbond.bond.notes:
            tracking_line += (
                '<dl class="bond_notes"><dt>Note:</dt><dd>%s</dl>' %
                srbond.bond.notes)
        elif has_interior_notes:
            # Put in a blank dl to make the spacing uniform.
            tracking_line += '<dl></dl>'

    return mark_safe(tracking_line)


@register.filter
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


@register.filter
def index_status_css(issue):
    """
    Text form of issue indexing status.  If clauses arranged in order of most
    likely case to least.
    """
    from apps.oi.templatetags.editing import is_locked

    if is_locked(issue):
        active = issue.revisions.get(changeset__state__in=states.ACTIVE)
        return STATE_CSS_NAME[active.changeset.state]
    elif issue.is_indexed == INDEXED['full']:
        return 'approved'
    elif issue.is_indexed in [INDEXED['partial'], INDEXED['ten_percent']]:
        return 'partial'
    else:
        return 'available'


@register.filter
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


def compare_field_between_revs(field, rev, prev_rev):
    old = getattr(prev_rev, field)
    new = getattr(rev, field)
    if type(new) == unicode:
        field_changed = old.strip() != new.strip()
    else:
        # TODO should be not hard-coded
        import apps.stddata.models
        if type(old) == apps.stddata.models.Date:
            field_changed = str(old) != str(new)
        else:
            field_changed = old != new
    return field_changed


@register.filter
def changed_fields(changeset, object):
    """
    get a human readable list of fields changed in a given approved changeset
    """
    object_class = type(object)
    if object_class is Issue:
        revision = changeset.issuerevisions.get(issue=object.id)
    elif object_class is Series:
        revision = changeset.seriesrevisions.get(series=object.id)
    elif object_class is SeriesBond:
        revision = changeset.seriesbondrevisions.get(series_bond=object.id)
    elif object_class is Publisher:
        revision = changeset.publisherrevisions.get(publisher=object.id)
    elif object_class is Brand:
        revision = changeset.brandrevisions.get(brand=object.id)
    elif object_class is BrandGroup:
        revision = changeset.brandgrouprevisions.get(brand_group=object.id)
    elif object_class is IndiciaPublisher:
        revision = changeset.indiciapublisherrevisions.all()\
                            .get(indicia_publisher=object.id)
    elif object_class is Award:
        revision = changeset.awardrevisions.get(award=object.id)
    elif object_class is ReceivedAward:
        revision = changeset.receivedawardrevisions.get(received_award=object.id)
    elif object_class is Creator:
        revision = changeset.creatorrevisions.get(creator=object.id)
    elif object_class is CreatorMembership:
        revision = changeset.creatormembershiprevisions\
                            .get(creator_membership=object.id)
    elif object_class is CreatorArtInfluence:
        revision = changeset.creatorartinfluencerevisions\
                            .get(creator_art_influence=object.id)
    elif object_class is CreatorDegree:
        revision = changeset.creatordegreerevisions\
                            .get(creator_degree=object.id)
    elif object_class is CreatorNonComicWork:
        revision = changeset.creatornoncomicworkrevisions\
                            .get(creator_non_comic_work=object.id)
    elif object_class in [Cover, Image]:
        return ""

    prev_rev = revision.previous()
    changed_list = []
    if prev_rev is None:
        # There was no previous revision so only list the initial add of
        # the object. Otherwise too many fields to list.
        changed_list = [u'%s added' % title(revision.source_name
                                                    .replace('_', ' '))]
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


@register.filter
def changed_story_list(changeset):
    """
    get a bulleted list of changes at the sequence level
    """
    if changeset.issuerevisions.count() and \
       changeset.change_type != CTYPES['issue_bulk']:
        # only relevant for single issue changesets
        story_revisions = changeset.storyrevisions.all()\
                                   .order_by('sequence_number')
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


@register.filter
def field_name(field):
    """
    translate field name into more human friendly name
    """
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
    elif field == 'cr_creator_names':
        return u'Creator Names'
    else:
        return title(field.replace('_', ' '))


@register.filter
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


@register.filter
def key(d, key_name):
    try:
        value = d[key_name]
    except KeyError:
        from django.conf import settings

        value = settings.TEMPLATE_STRING_IF_INVALID

    return value


@register.filter
def str_encl(string, bracket):
    if string:
        if bracket == '(':
            return '(' + string + ')'
        elif bracket == '[':
            return '[' + string + ']'
        elif bracket == '{':
            return '{' + string + '}'
    return string


@register.filter
def object_filter(search_result):
    if hasattr(search_result, 'object'):
        return search_result.object
    else:
        return search_result


@register.filter
def current_search(selected, search):
    if selected:
        if search == selected:
            return mark_safe('"%s" selected' % search)
    else:
        if search == 'haystack':
            return mark_safe('"%s" selected' % search)
    return mark_safe('"%s"' % search)


@register.filter
def short_pub_type(publication_type):
    if publication_type:
        return '[' + publication_type.name[0] + ']'
    else:
        return ''
