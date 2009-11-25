# -*- coding: utf-8 -*-
import re

from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue, Country, Language
from migration.reprints import split_reprint_string

register = template.Library()


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

    style = None
    if re.search(',', credit):
        [credit, style] = re.split(r',\s*', credit)
    
    if credit.startswith('any:'):
        target = credit[4:]
        credit_string = ''
        for c in ['script', 'pencils', 'inks', 'colors', 'letters', 'editing']:
            if getattr(story, c).lower().find(target.lower()) != -1:
              credit_string += ' ' + __format_credit(story, c, style)
        return credit_string

    elif hasattr(story, credit):
        return __format_credit(story, credit, style)

    else:
        return ""

def __credit_visible(value):
    """
    Check if credit exists and if we want to show it.
    This used to be a bit more complicated but it's very simple now.
    """
    return value is not None and value != ''


def __format_credit(story, credit, style):
    credit_value = getattr(story, credit)
    if not __credit_visible(credit_value):
        return ''

    if (credit == 'job_number'):
        label = _('Job Number:')
    else:
        label = _(credit.title()) + ':'

    if (credit == 'reprint_notes'):
        label = _('Reprinted:')
        values = split_reprint_string(credit_value)
        credit_value = '<ul>'
        for value in values:
            credit_value += '<li>' + esc(value)
        credit_value += '</ul>'
    else: # This takes care of escaping the database entries we display
        credit_value = esc(credit_value)
    dt = '<dt class="credit_tag'
    dd = '<dd class="credit_def'
    if (style):
        dt += ' %s' % style
        dd += ' %s' % style
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
    if story.sequence_number == 0:
        required_remaining += 1

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
    if issue_number == '[nn]':
        return u''
    return mark_safe('<span id="issue_number"><span class="p">#</span>' + \
        esc(issue_number) + '</span>')

def show_page_count(story):
    """
    Return a properly formatted page count, with "?" as needed.
    """
    if story is None:
        return u''

    if story.page_count is None:
        if story.page_count_uncertain:
            return u'?'
        return u''

    p = re.sub(r'\.?0+$', '', unicode(story.page_count))
    if story.page_count_uncertain:
        p = u'%s ?' % p
    return p

def show_title(story):
    """
    Return a properly formatted title.
    """
    if story.title == '':
        return u'[no title indexed]'
    if story.title_inferred:
        return u'[%s]' % story.title
    return story.title

register.filter(show_credit)
register.filter(show_credit_status)
register.filter(show_country)
register.filter(show_language)
register.filter(show_issue_number)
register.filter(show_page_count)
register.filter(show_title)

