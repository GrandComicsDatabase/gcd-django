from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template
from django.template.defaultfilters import pluralize

from apps.gcd.models import Issue

register = template.Library()

def show_have_want(issue, user):
    count = issue.collectionitem_set.filter(collections__name='Default have collection', collections__collector__user=user).count()
    if count:
        text = u'I have {} cop{} of this comic.'.format(count, pluralize(count, "y,ies"))
    else:
        text = u''

    count = issue.collectionitem_set.filter(collections__name='Default want collection', collections__collector__user=user).count()
    if count:
        if text != '':
            text += '<br>'
        text += u'This comic is on my want list.'

    return mark_safe(text)

register.filter(show_have_want)
