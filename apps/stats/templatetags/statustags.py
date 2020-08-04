# -*- coding: utf-8 -*-
from django import template
from django.utils.html import conditional_escape as esc
from django.utils.safestring import mark_safe

from apps.stats.models import RecentIndexedIssue

register = template.Library()

LANGUAGES=['de']

def last_updated_issues(parser, token):
    """
    Display the last updated indexes as a tag
    token is the content of the tag:
    last_updated_issues language=<language_code>
    where both language is optional
    The number of issues shown is configured in the settings as RECENTS_COUNT
    """

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

    return LastUpdatedNode(language_code, language_in_context)


class LastUpdatedNode(template.Node):
    def __init__(self, language_code, language_in_context):
        if language_in_context:
            self.language_in_context = template.Variable(language_in_context)
        else:
            self.language_in_context = None
        self.language_code = language_code

    def render(self, context):
        if self.language_in_context:
            try:
                self.language_code = self.language_in_context.resolve(context)
            except: # render in templates should fail silently
                return ''

        recents = RecentIndexedIssue.objects.select_related(
          'language', 'issue__series__publisher').order_by('-created')
        if self.language_code:
            recents = recents.filter(language__code=self.language_code)
        else:
            recents = recents.filter(language__isnull=True)

        return_string = '<ul>'
        for recent in recents:
            i = recent.issue
            return_string += '<li><a href="%s">%s</a> (%s)</li>' % \
                             (i.get_absolute_url(), esc(i.short_name()),
                              esc(i.series.publisher.name))

        return mark_safe(return_string+'</ul>')


register.tag('last_updated_issues', last_updated_issues)
