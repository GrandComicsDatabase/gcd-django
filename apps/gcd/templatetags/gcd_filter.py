from apps.gcd.models import Story
from django import template
from django.utils.translation import ugettext as _

register = template.Library()

def show_credit(story,credit):
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
    elif credit == 'job':
        return _('Job number')+": "+story.job_number
    elif credit == 'title':
        return _('Title')+": "+story.title
    else:
        return ""

register.filter(show_credit)
