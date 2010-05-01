# -*- coding: utf-8 -*-
from django import template
from django.utils.html import conditional_escape as esc
from django.utils.safestring import mark_safe

from apps.oi.models import IssueRevision, states

register = template.Library()


def last_updated_issues(parser, token):
    """
    Display the last updated indexes as a tag
    token is the content of the tag:
    last_updated_issues <number> language=<language_code>
    where both number and language are optional
    """
    try:
        number = int(token.split_contents()[1])
    except:
        number = 5
    issues = IssueRevision.objects.filter(issue__story_type_count__gt=0, 
      changeset__state=states.APPROVED).order_by('-changeset__modified')\
      .select_related('issue', 'issue__series', 'issue__series__publisher')

    language_pos = token.contents.find('language')
    if language_pos > 0:
        language_pos += len('language=')
        code = token.contents[language_pos:].lower()
        issues = issues.filter(issue__series__language__code=code)

    last_updated_issues = issues[:number]
    return LastUpdatedNode(last_updated_issues)


class LastUpdatedNode(template.Node):
    def __init__(self, issues):
        self.issues = issues
    def render(self, context):
        return_string = u''
        for issue_revision in self.issues:
            i = issue_revision.issue
            return_string += u'<a href="%s">%s #%s</a> (%s)<br><br>' % \
                             (i.get_absolute_url(), esc(i.series),
                              esc(i.number), esc(i.series.publisher.name))
        
        # 8 = len('<br><br>') to cut off last line break
        return mark_safe(return_string[:-8])


register.tag('last_updated_issues', last_updated_issues)
