from django import template
from django.utils.translation import ugettext as _

from apps.gcd.models import Issue

register = template.Library()


def show_credit(story, credit):
    """ For showing the credits on the search results page."""

    if credit.startswith('any:'):
        target = credit[4:]
        credit_string = ''
        for c in ['script', 'pencils', 'inks', 'colors', 'letters', 'editor']:
            if story.__dict__[c].find(target) != -1:
              credit_string += ' ' + __format_credit(story, c)
        return credit_string

    elif story.__dict__.has_key(credit):
        return __format_credit(story, credit)

    else:
        return ""


def __credit_visible(value):
    """ Check if credit exists and if we want to show it.  Could add
    further conditions for not showing the credit here."""
    return value and value.lower != 'none'


def __format_credit(story, credit):
    credit_value = story.__dict__[credit]
    if not __credit_visible(credit_value):
        return ''

    if (credit == 'job'):
        credit = 'job_number'
        label = 'Job Number'
    else:
        label = credit.title()

    return '<dt><span class="credit-label">' + _(label) + '</span></dt>' + \
           '<dd>' + credit_value + '</dd>'


register.filter(show_credit)
