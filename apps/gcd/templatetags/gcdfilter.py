from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from apps.gcd.models import Issue,Story

register = template.Library()

def show_credit(story,credit):
    """ For showing the credits on the search results page."""
    
    if credit == 'script':
        return _('Script')+": "+story.script
    elif credit == 'pencils':
        return _('Pencils')+": "+story.pencils
    elif credit == 'inks':
        return _('Inks')+": "+story.inks
    elif credit == 'colors':
        return _('Colors')+": "+story.colors
    elif credit == 'letters':
        return _('Letters')+": "+story.letters
    elif credit == 'editor':
        return _('Editor')+": "+story.editor
    elif credit == 'job':
        return _('Job number')+": "+story.job_number
    elif credit == 'title':
        return _('Title')+": "+story.title
    elif credit.startswith('any:'):
        credit_string=""
        if story.script.find(credit[4:]) != -1:
            credit_string += _('Script')+": "+story.script
        if story.pencils.find(credit[4:]) != -1:
            credit_string += _('Pencils')+": "+story.pencils
        if story.inks.find(credit[4:]) != -1:
            credit_string += _('Inks')+": "+story.inks
        if story.colors.find(credit[4:]) != -1:
            credit_string += _('Colors')+": "+story.colors
        if story.letters.find(credit[4:]) != -1:
            credit_string += _('Letters')+": "+story.letters
        if story.editor.find(credit[4:]) != -1:
            credit_string += _('Editor')+": "+story.editor
        return credit_string
    else:
        return ""


# we may want to move this somewhere else
def is_visible_credit(credit):
    """ Check if credit exists and if we want to show it.  Could add
    further conditions for not showing the credit here."""
     
    if credit:
        if credit.lower != 'none':
            return True
    return False


def show_details(story,credit):
    """ For showing the credits on the issue page."""
    
    if credit == 'script':
        if is_visible_credit(story.script):
            return story.script + " (" + _('Script') + "), "
    elif credit == 'pencils':
        if is_visible_credit(story.pencils):
            return story.pencils + " ("+_('Pencils')+"), "
    elif credit == 'inks':
        if is_visible_credit(story.inks):
            return story.inks + " ("+_('Inks')+"), "
    elif credit == 'colors':
        if is_visible_credit(story.colors):
            return story.colors +" ("+_('Colors')+"), "
    elif credit == 'letters':
        if is_visible_credit(story.letters):
            return story.letters +" ("+_('Letters')+")."
    elif credit == 'editor':
        if is_visible_credit(story.editor):
            return story.editor +" ("+_('Editor')+")."
    elif credit == 'job':
        return _('Job number')+": "+story.job_number
    else:
        return ""
    return ""

register.filter(show_credit)
register.filter(show_details)
