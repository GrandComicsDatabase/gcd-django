# -*- coding: utf-8 -*-
from django import template
from django.utils.html import conditional_escape as esc
from django.utils.safestring import mark_safe

from apps.oi.models import IssueRevision, states, CTYPES

register = template.Library()

LANGUAGES=['de']

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

    language_in_context = None
    language_code = None
    language_pos = token.contents.find('language')
    if language_pos > 0:
        language_pos += len('language=')
        code = token.contents[language_pos:].lower().strip()
        if code in LANGUAGES: # either a supported language code 
            language_code = code
        else: # or the language_code via a template variable
            language_in_context = code

    return LastUpdatedNode(number, language_code, language_in_context)


class LastUpdatedNode(template.Node):
    def __init__(self, number, language_code, language_in_context):
        if language_in_context:
            self.language_in_context = template.Variable(language_in_context)
        else:
            self.language_in_context = None
        self.language_code = language_code
        self.number = number

    def render(self, context):
        if self.language_in_context:
            try:
                self.language_code = self.language_in_context.resolve(context)
            except: # render in templates should fail silently
                return u''

        issues = IssueRevision.objects.filter(issue__story_type_count__gt=0, 
          changeset__change_type=CTYPES['issue'],
          changeset__state=states.APPROVED).order_by('-changeset__modified')\
            .select_related('issue', 'issue__series', 'issue__series__publisher')
        if self.language_code:
            issues = issues.filter(issue__series__language__code=self.language_code)
 
        last_updated_issues = issues[:self.number]
        return_string = u''
        for issue_revision in last_updated_issues:
            i = issue_revision.issue
            return_string += u'<a href="%s">%s #%s</a> (%s)<br><br>' % \
                             (i.get_absolute_url(), esc(i.series),
                              esc(i.number), esc(i.series.publisher.name))
        
        # 8 = len('<br><br>') to cut off last line break
        return mark_safe(return_string[:-8])


register.tag('last_updated_issues', last_updated_issues)
