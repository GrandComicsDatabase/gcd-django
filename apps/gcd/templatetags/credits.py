import re

from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue

register = template.Library()


def show_credit(story, credit):
    """ For showing the credits on the search results page.
    As far as I can tell Django template filters can only take
    one argument, hence the icky splitting of 'credit'.  Suggestions
    on a better way welcome, as clearly I'm abusing the Django filter
    convention here."""

    if not story:
        return ""

    style = None
    if re.search(',', credit):
        [credit, style] = re.split(r',\s*', credit)
    
    if credit.startswith('any:'):
        target = credit[4:]
        credit_string = ''
        for c in ['script', 'pencils', 'inks', 'colors', 'letters', 'editor']:
            if story.__dict__[c].find(target) != -1:
              credit_string += ' ' + __format_credit(story, c, style)
        return credit_string

    elif story.__dict__.has_key(credit):
        return __format_credit(story, credit, style)

    elif (credit == 'job'):
        return __format_credit(story, 'job_number', style)
        
    else:
        return ""

def show_form(field):
    """ For showing form fields for credits and similar fields."""
    return mark_safe('<li>' + field.label_tag() + unicode(field) + \
                     unicode(field.errors))

def __credit_visible(value):
    """ Check if credit exists and if we want to show it.  Could add
    further conditions for not showing the credit here."""
    return value and value.lower != 'none'


def __format_credit(story, credit, style):
    credit_value = story.__dict__[credit]
    if not __credit_visible(credit_value):
        return ''


    if (credit == 'job_number'):
        label = _('Job Number:')
    else:
        label = _(credit.title()) + ':'

    if (credit == 'reprints'):
        credit_value = '<ul><li>' + re.sub(r';\s*', "<li>", esc(credit_value)) + \
                       '</ul>'
        # TODO: Deal with style parameter / setting.
        label += ' <span class="linkify"><a href="?reprints=True">' + \
                 _('search and link') + '</a></span>'
    else: # This takes care of escaping the database entries we display
        credit_value = esc(credit_value)
    dt = '<dt class="credit_tag'
    dd = '<dd class="credit_def'
    if (style):
        dt += ' %s' % style
        dd += ' %s' % style
    dt += '">'
    dd += '">'

    return mark_safe(dt + '<span class="credit_label">' + label + '</span></dt>' + \
           dd + '<span class="credit_value">' + credit_value + '</span></dd>')


register.filter(show_credit)
register.filter(show_form)
