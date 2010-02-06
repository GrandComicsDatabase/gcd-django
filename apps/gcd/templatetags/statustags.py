# -*- coding: utf-8 -*-
from django import template
from django.utils.html import conditional_escape as esc
from django.utils.safestring import mark_safe

from apps.gcd.models import Issue

register = template.Library()


def last_updated_issues(parser, token):
    """
    Display the <number> last updated indexes as a tag
    """
    try:
        number = int(token.split_contents()[1])
    except:
        number = 5
    issues = Issue.objects.filter(story_type_count__gt=0, reserved=False)\
				  .order_by('-modified')\
                                  .select_related('series', 'series__publisher')
    last_updated_issues = issues[:number]
    return LastUpdatedNode(last_updated_issues)


class LastUpdatedNode(template.Node):
    def __init__(self, issues):
        self.issues = issues
    def render(self, context):
        return_string = ""
        for i in self.issues:
            return_string += "<a href=\"" + i.get_absolute_url() + "\">" + \
                             esc(i.series) + " #" + esc(i.number) + "</a> (" + \
                             esc(i.series.publisher.name) + ")<br/><br/>"
        return mark_safe(return_string)


register.tag('last_updated_issues', last_updated_issues)
