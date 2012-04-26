# -*- coding: utf-8 -*-
import re
try:
   import icu
except:
   import PyICU as icu

from django import template
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue, Country, Language, Reprint
from apps.oi.models import ReprintRevision

register = template.Library()

def sc_in_brackets(reprints, bracket_begin, bracket_end, sc_pos):
    begin = reprints.find(bracket_begin)
    end = reprints.find(bracket_end)
    if sc_pos in range(begin, end):
        sc_pos = reprints[end:].find(';')
        if sc_pos > -1:
            return end + sc_pos
        else:
            return -1
    else:
        return sc_pos

def split_reprint_string(reprints):
    '''
    split the reprint string
    need our own routine to take care of the ';' in publisher names and notes
    '''
    liste = []
    sc_pos = reprints.find(';')
    while sc_pos > -1:
        sc_pos = sc_in_brackets(reprints, '(', ')', sc_pos)
        sc_pos = sc_in_brackets(reprints, '[', ']', sc_pos)
        if sc_pos > -1:
            liste.append(reprints[:sc_pos].strip())
            reprints = reprints[sc_pos+1:]
            sc_pos = reprints.find(';')
    liste.append(reprints.strip())
    return liste

def show_credit(story, credit):
    """
    For showing the credits on the search results page.
    As far as I can tell Django template filters can only take
    one argument, hence the icky splitting of 'credit'.  Suggestions
    on a better way welcome, as clearly I'm abusing the Django filter
    convention here.
    """

    if not story:
        return ""

    if credit.startswith('any:'):
        collator = icu.Collator.createInstance()
        collator.setStrength(0) # so that umlaut/accent behave as in MySql
        target = credit[4:]
        credit_string = ''
        for c in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing']:
            story_credit = getattr(story, c).lower()
            if story_credit:
                search = icu.StringSearch(target.lower(),
                                          story_credit,
                                          collator)
                if search.first() != -1:
                    credit_string += ' ' + __format_credit(story, c)
        if story.issue.editing:
            search = icu.StringSearch(target.lower(),
                                      story.issue.editing.lower(),
                                      collator)
            if search.first() != -1:
                credit_string += __format_credit(story.issue, 'editing')\
                             .replace('Editing', 'Issue editing')
        return credit_string

    elif credit.startswith('editing_search:'):
        collator = icu.Collator.createInstance()
        collator.setStrength(0)
        target = credit[15:]
        formatted_credit = ""
        if story.editing:
            search = icu.StringSearch(target.lower(),
                                      story.editing.lower(),
                                      collator)
            if search.first() != -1:
                formatted_credit = __format_credit(story, 'editing')\
                                   .replace('Editing', 'Story editing')

        if story.issue.editing:
            search = icu.StringSearch(target.lower(),
                                      story.issue.editing.lower(),
                                      collator)
            if search.first() != -1:
                formatted_credit += __format_credit(story.issue, 'editing')\
                                    .replace('Editing', 'Issue editing')
        return formatted_credit

    elif credit.startswith('characters:'):
        collator = icu.Collator.createInstance()
        collator.setStrength(0)
        target = credit[len('characters:'):]
        formatted_credit = ""
        if story.characters:
            search = icu.StringSearch(target.lower(),
                                      story.characters.lower(),
                                      collator)
            if search.first() != -1:
                formatted_credit = __format_credit(story, 'characters')

        if story.feature:
            search = icu.StringSearch(target.lower(),
                                      story.feature.lower(),
                                      collator)
            if search.first() != -1:
                formatted_credit += __format_credit(story, 'feature')
        return formatted_credit

    elif hasattr(story, credit):
        return __format_credit(story, credit)

    else:
        return ""

def __credit_visible(value):
    """
    Check if credit exists and if we want to show it.
    This used to be a bit more complicated but it's very simple now.
    """
    return value is not None and value != ''


def __format_credit(story, credit):
    credit_value = getattr(story, credit)
    if not __credit_visible(credit_value):
        return ''

    if (credit == 'job_number'):
        label = _('Job Number:')
    else:
        label = _(credit.title()) + ':'

    if (credit in ['reprint_notes', 'reprint_original_notes']):
        label = _('Reprinted:')
        values = split_reprint_string(credit_value)
        credit_value = '<ul>'
        for value in values:
            credit_value += '<li>' + esc(value)
        credit_value += '</ul>'
    elif credit == 'keywords':
        if type(story.keywords) == unicode:
            credit_value = story.keywords
        else:
            credit_value = esc('; '.join(str(i) for i in story.keywords.all().order_by('name')))
        if credit_value == '':
            return ''
    else: # This takes care of escaping the database entries we display
        credit_value = esc(credit_value)
    dt = '<dt class="credit_tag'
    dd = '<dd class="credit_def'
    if credit == 'genre':
        dt += ' short'
        dd += ' short'
    dt += '">'
    dd += '">'

    return mark_safe(
           dt + '<span class="credit_label">' + label + '</span></dt>' + \
           dd + '<span class="credit_value">' + credit_value + '</span></dd>')

def show_credit_status(story):
    """
    Display a set of letters indicating which of the required credit fields
    have been filled out.  Technically, the editing field is not required but
    it has historically been displayed as well.  The required editing field
    is now directly on the issue record.
    """
    status = []
    required_remaining = 5

    if story.script or story.no_script:
        status.append('S')
        required_remaining -= 1

    if story.pencils or story.no_pencils:
        status.append('P')
        required_remaining -= 1

    if story.inks or story.no_inks:
        status.append('I')
        required_remaining -= 1

    if story.colors or story.no_colors:
        status.append('C')
        required_remaining -= 1

    if story.letters or story.no_letters:
        status.append('L')
        required_remaining -= 1

    if story.editing or story.no_editing:
        status.append('E')

    completion = 'complete'
    if required_remaining:
        completion = 'incomplete'
    snippet = '[<span class="%s">' % completion
    snippet += ' '.join(status)
    snippet += '</span>]'
    return mark_safe(snippet)


def show_cover_contributor(cover_revision):
    if cover_revision.file_source:
        if cover_revision.changeset.indexer.id == 381: # anon user
            # filter away '( email@domain.part )' for old contributions
            text = cover_revision.file_source
            bracket = text.rfind('(')
            if bracket >= 0:
                return text[:bracket]
            else:
                return text
        else:
            return unicode(cover_revision.changeset.indexer.indexer) + \
              ' (from ' + cover_revision.file_source + ')'
    else:
        return cover_revision.changeset.indexer.indexer


# these next three might better fit into a different file

def show_country(series):
    """
    Translate country code into country name.
    Formerly had to do real work when we did not have foreign keys.
    """
    return unicode(series.country)


def show_language(series):
    """
    Translate country code into country name.
    Formerly had to do real work when we did not have foreign keys.
    """
    return unicode(series.language)

def show_issue_number(issue_number):
    """
    Return issue number, unless it is marked as not having one.
    """
    return mark_safe('<span class="issue_number"><span class="p">#</span>' + \
        esc(issue_number) + '</span>')

def show_page_count(story, show_page=False):
    """
    Return a properly formatted page count, with "?" as needed.
    """
    if story is None:
        return u''

    if story.page_count is None:
        if story.page_count_uncertain:
            return u'?'
        return u''

    p = format_page_count(story.page_count)
    if story.page_count_uncertain:
        p = u'%s ?' % p
    if show_page:
        p = p + u' ' + ungettext('page', 'pages', story.page_count)
    return p

def format_page_count(page_count):
    if page_count is not None:
        return re.sub(r'\.?0+$', '', unicode(page_count))
    else:
        return u''

def show_title(story):
    """
    Return a properly formatted title.
    """
    if story is None:
        return u''
    if story.title == '':
        return u'[no title indexed]'
    if story.title_inferred:
        return u'[%s]' % story.title
    return story.title

def generate_reprint_link(issue, from_to, notes=None, li=True):
    ''' generate reprint link to_issue'''

    link = u'%s <a href="%s">%s</a>' % (from_to, issue.get_absolute_url(),
                                        esc(issue.full_name()) )

    if issue.publication_date:
        link += " (" + esc(issue.publication_date) + ")"
    if notes:
        link = '%s [%s]' % (link, esc(notes))
    if li:
        return '<li> ' + link + ' </li>'
    else:
        return link


def generate_reprint_link_sequence(story, from_to, notes=None, li=True):
    ''' generate reprint link to story'''

    link = u'%s <a href="%s#%d">%s</a>' % (from_to, story.issue.get_absolute_url(),
                                           story.id, esc(story.issue.full_name()) )
    if story.issue.publication_date:
        link = "%s (%s)" % (link, esc(story.issue.publication_date))
    if notes:
        link = '%s [%s]' % (link, esc(notes))
    if li:
        return '<li> ' + link + ' </li>'
    else:
        return link

# stuff to consider in the display
# - sort domestic/foreign reprints

def follow_reprint_link(reprint, direction, level=0):
    reprint_note = 'which is reprinted<ul>'
    text = False
    if direction == 'from':
        further_reprints = list(reprint.origin.from_reprints.select_related().all())
        further_reprints.extend(list(reprint.origin.from_issue_reprints.select_related().all()))
        further_reprints = sorted(further_reprints, key=lambda a: a.origin_sort)
        if reprint.origin.reprint_notes:
            for string in split_reprint_string(reprint.origin.reprint_notes):
                string = string.strip()
                if string.lower().startswith('from '):
                    text = True
                    reprint_note += '<li> ' + esc(string) + ' </li>'
    else:
        further_reprints = list(reprint.target.to_reprints.select_related().all())
        further_reprints.extend(list(reprint.target.to_issue_reprints.select_related().all()))
        further_reprints = sorted(further_reprints, key=lambda a: a.origin_sort)        
        if reprint.target.reprint_notes:
            for string in split_reprint_string(reprint.target.reprint_notes):
                string = string.strip()
                if string.lower().startswith('in '):
                    text = True
                    reprint_note += '<li> ' + esc(string) + ' </li>'
    if further_reprints:
        for further_reprint in further_reprints:
            if hasattr(further_reprint, 'origin_issue') and further_reprint.origin_issue:
                reprint_note += generate_reprint_link(further_reprint.origin_issue,
                                                direction,
                                                notes = further_reprint.notes)
            elif hasattr(further_reprint, 'target_issue') and further_reprint.target_issue:
                reprint_note += generate_reprint_link(further_reprint.target_issue,
                                                direction,
                                                notes = further_reprint.notes)
            else:
                if direction == 'from':                    
                    reprint_note += generate_reprint_link_sequence(further_reprint.origin,
                                                            direction,
                                                            notes = further_reprint.notes)
                else:
                    reprint_note += generate_reprint_link_sequence(further_reprint.target,
                                                            direction,
                                                            notes = further_reprint.notes)
                if level < 10: # max level to avoid loops
                    follow_reprint_link(further_reprint, direction, level=level+1)
        reprint_note += '</ul>'
        return reprint_note
    else:
        if text:
            return reprint_note + '</ul>'
        else:
            return ''
        
def show_reprints(story, original = False):
    """ Filter for our reprint line on the story level."""

    reprint = ""

    from_reprints = list(story.from_reprints.select_related().all())
    from_reprints.extend(list(story.from_issue_reprints.select_related().all()))
    from_reprints = sorted(from_reprints, key=lambda a: a.origin_sort)
    for from_reprint in from_reprints:
        if hasattr(from_reprint, 'origin_issue') and from_reprint.origin_issue:
            reprint += generate_reprint_link(from_reprint.origin_issue,
                                            "from ",
                                            notes = from_reprint.notes)
            if original == 'With_Story':
                reprint += 'points to issue'
        else:
            reprint += generate_reprint_link_sequence(from_reprint.origin,
                                                    "from ",
                                                    notes = from_reprint.notes)
            if original == 'With_Story':
                from apps.gcd.templatetags.display import show_story_short
                reprint += 'points to sequence: %s' % \
                  show_story_short(from_reprint.origin)
            reprint += follow_reprint_link(from_reprint, 'from')
                
    to_reprints = list(story.to_reprints.select_related().all())
    to_reprints.extend(list(story.to_issue_reprints.select_related().all()))
    to_reprints = sorted(to_reprints, key=lambda a: a.target_sort)
    for to_reprint in to_reprints:
        if hasattr(to_reprint, 'target_issue') and to_reprint.target_issue:
            reprint += generate_reprint_link(to_reprint.target_issue,
                                            "in ",
                                            notes = to_reprint.notes)
            if original == 'With_Story':
                reprint += 'points to issue'
        else:
            reprint += generate_reprint_link_sequence(to_reprint.target,
                                                    "in ",
                                                    notes = to_reprint.notes)
            if original == 'With_Story':
                from apps.gcd.templatetags.display import show_story_short
                reprint += 'points to sequence: %s' % \
                  show_story_short(to_reprint.target)
            reprint += follow_reprint_link(to_reprint, 'in')
    
    if story.reprint_notes:
        for string in split_reprint_string(story.reprint_notes):
            string = string.strip()
            reprint += '<li> ' + esc(string) + ' </li>'
    if reprint != '' or (original and not story.reprint_confirmed and \
                         story.migration_status.reprint_original_notes):
        label = _('Reprints') + ': '
        if original:
            if not story.reprint_confirmed and \
              story.migration_status.reprint_original_notes:
                reprint += '</ul></span></dd>' + \
                  '<dt class="credit_tag">' + '<span class="credit_label">' + \
                  'Reprint Note before Migration: </span></dt>' + \
                  '<dd class="credit_def"><span class="credit_value"><ul>'
                for string in split_reprint_string(story.migration_status.
                                                   reprint_original_notes):
                    string = string.strip()
                    reprint += '<li> ' + esc(string) + ' </li>'
                  #story.migration_status.reprint_original_notes + '</dd></span>'
        else:
            if not story.reprint_confirmed:
                label += '<span class="linkify">' + \
                        '<a href="?original_reprint_notes=True">' + \
                        'show reprint note before migration</a></span>'
            if story.reprint_needs_inspection:
                label += ' (migrated reprint links need inspection)'

        return mark_safe('<dt class="credit_tag">' + \
                         '<span class="credit_label">' + label + '</span></dt>' + \
                         '<dd class="credit_def">' + \
                         '<span class="credit_value">' + \
                         '<ul>' + reprint + '</ul></span></dd>')
    else:
        return ""

def show_reprints_for_issue(issue):
    """ show reprints stored on the issue level. """

    reprint = ""
    from_reprints = list(issue.from_reprints.select_related().all())
    from_reprints.extend(list(issue.from_issue_reprints.select_related().all()))
    from_reprints = sorted(from_reprints, key=lambda a: a.origin_sort)
    for from_reprint in from_reprints:
        if hasattr(from_reprint, 'origin_issue') and from_reprint.origin_issue:
            reprint += generate_reprint_link(from_reprint.origin_issue,
                                            "from ",
                                            notes = from_reprint.notes)
        else:
            reprint += generate_reprint_link_sequence(from_reprint.origin,
                                                    "from ",
                                                    notes = from_reprint.notes)
            reprint += follow_reprint_link(from_reprint, 'from')

    to_reprints = list(issue.to_reprints.select_related().all())
    to_reprints.extend(list(issue.to_issue_reprints.select_related().all()))
    to_reprints = sorted(to_reprints, key=lambda a: a.target_sort)
    for to_reprint in to_reprints:
        if hasattr(to_reprint, 'target_issue') and to_reprint.target_issue:
            reprint += generate_reprint_link(to_reprint.target_issue,
                                            "in ",
                                            notes = to_reprint.notes)
        else:
            reprint += generate_reprint_link_sequence(to_reprint.target,
                                                    "in ",
                                                    notes = to_reprint.notes)
            reprint += follow_reprint_link(to_reprint, 'in')
                                                    
    if reprint != '':
        label = _('Parts of this issue are reprinted') + ': '
        dt = '<dt class="credit_tag>'
        dd = '<dd class="credit_def>'

        return mark_safe(dt + '<span class="credit_label">' + label + '</span></dt>' + \
               dd + '<span class="credit_value"><ul>' + reprint + '</ul></span></dd>')
    else:
        return ""

register.filter(show_credit)
register.filter(show_credit_status)
register.filter(show_country)
register.filter(show_language)
register.filter(show_issue_number)
register.filter(show_page_count)
register.filter(format_page_count)
register.filter(show_title)
register.filter(show_cover_contributor)
register.filter(show_reprints)
register.filter(show_reprints_for_issue)
register.filter(split_reprint_string)
