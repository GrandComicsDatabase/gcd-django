# -*- coding: utf-8 -*-
from decimal import Decimal
from stdnum import ean as stdean
from stdnum import isbn as stdisbn

from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc
from django.conf import settings

from django import template
from django.template.defaultfilters import title

from apps.oi import states
from apps.oi.models import CTYPES
from apps.gcd.templatetags.credits import show_page_count
from apps.gcd.models import Creator, CreatorMembership, ReceivedAward, \
                                    CreatorArtInfluence, CreatorNonComicWork, \
                                    CreatorDegree, CreatorRelation, \
                                    CreatorSchool, CreatorSignature, Award
from apps.gcd.models import Publisher, IndiciaPublisher, Brand, BrandGroup, \
                            Series, Issue, Cover, Image, \
                            Feature, FeatureLogo, \
                            Character, Group, CharacterRelation, \
                            GroupRelation, GroupMembership, Universe, \
                            INDEXED, SeriesBond, BOND_TRACKING, \
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


@register.filter(name='split')
def split(value):
    if value:
        return value.split(';')
    else:
        return ''


@register.filter
def absolute_url(item, popup=None, descriptor=''):
    if item is not None and hasattr(item, 'get_absolute_url'):
        if descriptor == '':
            descriptor = esc(item)
        if popup and not settings.FAKE_IMAGES:
            image_link = '<span class="image_popup opacity-0 ease-in-out ' \
                         'delay-100 duration-300 absolute transition-opacity' \
                         ' group-hover:opacity-100"><img src="%s"></span>' \
                         % popup.thumbnail.url
            return mark_safe('<a href="%s" class="group popup">%s%s</a>' %
                             (item.get_absolute_url(), descriptor, image_link))
        else:
            return mark_safe('<a href="%s">%s</a>' %
                             (item.get_absolute_url(), descriptor))
    return ''


@register.filter
def cover_image_tag(cover, size_alt_text):
    size, alt_text = size_alt_text.split(',')
    return get_image_tag(cover, alt_text, int(size))


@register.filter
def show_story_short(story, no_number=False, markup=True):
    if no_number:
        story_line = ''
    else:
        story_line = '%s.' % story.sequence_number

    if story.title or story.first_line:
        title = story.show_title(True)
    else:
        if markup:
            title = mark_safe('<span class="italic">no title</span>')
        else:
            title = 'no title'
    if story.has_feature():
        if markup:
            story_line = '%s %s (%s)' % (esc(story_line), esc(title),
                                         esc(story.show_feature()))
        else:
            story_line = '%s %s (%s)' % (story_line, title,
                                         story.show_feature_as_text())
    else:
        if markup:
            story_line = '%s %s (%s)' % (
              esc(story_line),
              title,
              '<span class="italic">no feature</span>')
        else:
            story_line = '%s %s (no feature)' % (esc(story_line), title)

    story_line = '%s %s' % (story_line, story.type)
    page_count = show_page_count(story)
    if page_count:
        story_line += ', %sp' % page_count
    else:
        if markup:
            story_line += '<span class="italic"> no page count</span>'
        else:
            story_line += 'no page count'
    if markup:
        return mark_safe(story_line)
    else:
        return story_line


@register.filter
def show_volume(issue):
    if issue.no_volume:
        return ''
    if issue.volume == '':
        return '?'
    if issue.volume_not_printed:
        return '[%s]' % issue.volume
    return issue.volume


@register.filter
def show_issue_number(issue_number):
    """
    Return issue number.
    """
    return mark_safe('<span class="issue_number">' + esc(issue_number) +
                     '</span>')


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
    return issue.show_series_and_issue_link()


@register.filter
def show_series_tracking(series):
    tracking_line = ""
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
            near_issue_preposition = "with"
            far_issue_preposition = "from"
            far_preposition = "from"
        elif series == srbond.bond.origin:
            near_issue_preposition = "after"
            far_issue_preposition = "with"
            far_preposition = "in"
            if srbond.bond.bond_type.id in MERGE_TRACKING:
                far_issue_preposition = "into"
                far_preposition = "into"
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
            ip_url = '[none printed]'
        else:
            ip_url = '?'
    else:
        ip_url = '<a href=\"%s\">%s</a>' % \
          (issue.indicia_publisher.get_absolute_url(), issue.indicia_publisher)
        if issue.indicia_pub_not_printed:
            ip_url += ' [not printed on item]'
    return mark_safe(ip_url)


@register.filter
def index_status_color(issue):
    """
    Color for issue indexing status. If clauses arranged in order of most
    likely case to least.
    """
    from apps.oi.templatetags.editing import is_locked

    if is_locked(issue):
        active = issue.revisions.get(changeset__state__in=states.ACTIVE)
        if active.changeset.state == states.OPEN:
            return 'bg-red-400'
        else:
            return 'bg-yellow-400'
    elif issue.is_indexed == INDEXED['full']:
        return 'bg-green-600'
    elif issue.is_indexed in [INDEXED['partial'], INDEXED['ten_percent']]:
        return 'bg-green-400'
    elif issue.is_indexed == INDEXED['some_data']:
        return 'bg-green-200'
    else:
        return ''


@register.filter
def issue_image_status_color(issue):
    """
    Color for issue image resources status.
    """
    if issue.sum_scans_code == 1:
        return 'bg-indigo-200'
    elif issue.sum_scans_code is None:
        return ''
    elif issue.sum_scans_code == 2:
        return 'bg-cyan-400'
    else:
        return 'bg-green-600'


# TODO: move to an oi-templatetags file
@register.filter
def show_revision_type(cover):
    if cover.deleted:
        return '[DELETED]'
    if cover.cover:
        if cover.cover.marked:
            return '[REPLACEMENT]'
        else:
            return '[SUGGESTED REPLACEMENT]'
    if cover.changeset.issuerevisions.count():
        return '[VARIANT]'
    if cover.issue.has_covers():
        return '[ADDITIONAL]'
    return '[ADDED]'


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
    elif object_class is Feature:
        revision = changeset.featurerevisions.get(feature=object.id)
    elif object_class is FeatureLogo:
        revision = changeset.featurelogorevisions.get(feature_logo=object.id)
    elif object_class is Universe:
        revision = changeset.universerevisions.get(universe=object.id)
    elif object_class is Character:
        revision = changeset.characterrevisions.get(character=object.id)
    elif object_class is Group:
        revision = changeset.grouprevisions.get(group=object.id)
    elif object_class is CharacterRelation:
        revision = changeset.characterrelationrevisions\
                            .get(character_relation=object.id)
    elif object_class is GroupRelation:
        revision = changeset.grouprelationrevisions\
                            .get(group_relation=object.id)
    elif object_class is GroupMembership:
        revision = changeset.groupmembershiprevisions\
                            .get(group_membership=object.id)
    elif object_class is Award:
        revision = changeset.awardrevisions.get(award=object.id)
    elif object_class is ReceivedAward:
        revision = changeset.receivedawardrevisions\
                            .get(received_award=object.id)
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
    elif object_class is CreatorRelation:
        revision = changeset.creatorrelationrevisions\
                            .get(creator_relation=object.id)
    elif object_class is CreatorSchool:
        revision = changeset.creatorschoolrevisions\
                            .get(creator_school=object.id)
    elif object_class is CreatorSignature:
        revision = changeset.creatorsignaturerevisions\
                            .get(creator_signature=object.id)
    elif object_class in [Cover, Image]:
        return ""

    changed_list = []
    if revision.added:
        # Only list the initial add of the object.
        # Otherwise too many fields to list.
        changed_list = ['%s added' % title(revision.source_name
                                                   .replace('_', ' '))]
    elif revision.deleted:
        changed_list = ['%s deleted' %
                        title(revision.source_name.replace('_', ' '))]
    else:
        revision.compare_changes()
        for field in revision._field_list():
            if revision.changed[field]:
                changed_list.append(field_name(field))
    return ", ".join(changed_list)


@register.filter
def changed_story_list(changeset):
    """
    get a bulleted list of changes at the sequence level
    """
    if changeset.issuerevisions.count() and \
       changeset.change_type not in [CTYPES['series'],
                                     CTYPES['issue_bulk']]:
        # only relevant for single issue changesets
        story_revisions = changeset.storyrevisions.all()\
                                   .order_by('sequence_number')
    else:
        return ''

    output = ''
    if story_revisions.count() > 0:
        for story_revision in story_revisions:
            story_changed_list = []
            if story_revision.added:
                story_changed_list = ['Sequence added']
            elif story_revision.deleted:
                story_changed_list = ['Sequence deleted']
            else:
                story_revision.compare_changes()
                for field in story_revision._field_list():
                    if story_revision.changed[field]:
                        story_changed_list.append(field_name(field))
            if story_changed_list:
                output += '<li>Sequence %s : %s' % \
                          (story_revision.sequence_number,
                           ", ".join(story_changed_list))
        if output != '':
            output = '<ul class="object-page-link-list">%s</ul>' % output
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
        return '%s?' % title(field.replace('is_', ''))
    elif field in ['url', 'isbn']:
        return field.upper()
    elif field == 'after':
        return 'Add Issue After'
    elif field == 'indicia_pub_not_printed':
        return 'Indicia Publisher Not Printed'
    elif field == 'title_inferred':
        return 'Unofficial Title?'
    elif field == 'cr_creator_names':
        return 'Creator Names'
    else:
        return title(field.replace('_', ' '))


@register.filter
def uncertain_year(object, field_name):
    """
    display year with uncertain information
    """
    year = object.__dict__[field_name] if object.__dict__[field_name] else ''
    if object.__dict__[field_name + '_uncertain']:
        year = '%s ?' % (year)
    return year


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


@register.filter
def pre_process_relation(relation, object):
    return relation.pre_process_relation(object)


@register.filter
def character_for_universe(character, universe):
    if character.active_specifications().filter(
       to_character__universe=universe).count() == 1:
        to_character = character.active_specifications()\
          .get(to_character__universe=universe).to_character
        return mark_safe(absolute_url(to_character,
                                      descriptor=to_character.descriptor(
                                        disambiguation=False)))
    else:
        return ''


@register.filter
def group_for_universe(group, universe):
    if group.active_specifications().filter(
       to_group__universe=universe).count() == 1:
        to_group = group.active_specifications()\
          .get(to_group__universe=universe).to_group
        return mark_safe(absolute_url(to_group,
                                      descriptor=to_group.descriptor(
                                        disambiguation=False)))
    else:
        return ''
