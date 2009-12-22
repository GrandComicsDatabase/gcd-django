from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template

register = template.Library()

def absolute_url(item, default=''):
    if item is not None:
        return mark_safe(u'<a href="%s">%s</a>' %
                         (item.get_absolute_url, esc(item)))
    return default

register.filter(absolute_url)

