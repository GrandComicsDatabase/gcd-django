from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape as esc

from django import template
from django.template.defaultfilters import pluralize
from apps.gcd.views.covers import get_image_tags_per_issue
from apps.gcd.models.cover import ZOOM_SMALL, ZOOM_MEDIUM

from apps.gcd.models import Issue

register = template.Library()

def show_have_want(issue, user):
    count = issue.collectionitem_set\
                 .filter(collections__collector__user=user).count()
    want_count = issue.collectionitem_set.filter(
        collections=user.collector.default_want_collection,
        collections__collector__user=user).count()
    count -= want_count
    if count:
        text = u'I have {} cop{} of this comic.'.format(count, pluralize(count,
                                                                    "y,ies"))
    else:
        text = u''

    if want_count:
        if text != '':
            text += '<br>'
        text += u'This comic is on my want list.'

    return mark_safe(text)


def show_cover_tag(issue):
    return get_image_tags_per_issue(issue, alt_text=u'', zoom_level=ZOOM_SMALL)


def show_cover_tag_medium(issue):
    return get_image_tags_per_issue(issue, alt_text=u'', zoom_level=ZOOM_MEDIUM)


@register.filter
def is_default_collection(collection):
    return (collection == collection.collector.default_want_collection) or (
      collection == collection.collector.default_have_collection)


register.filter(show_have_want)
register.filter(show_cover_tag)
register.filter(show_cover_tag_medium)