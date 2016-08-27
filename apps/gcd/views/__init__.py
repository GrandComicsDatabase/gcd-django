"""
Due to uncertainty about how to best structure things and the size of the app,
the models and views were split into multiple individual files instead of
the traditional models.py and views.py files.

This file contains the front page view, plus utilities for working with
requests, responses and errors.
"""

import hashlib
from random import random

from urllib import quote
from django.conf import settings
from django.core import urlresolvers
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.utils.safestring import mark_safe

from apps.gcd.views.pagination import DiggPaginator

from apps.stddata.models import Language
from apps.stats.models import CountStats
from apps.indexer.models import Error

ORDER_ALPHA = "alpha"
ORDER_CHRONO = "chrono"


def index(request):
    """Generates the front index page."""

    stats = CountStats.objects.filter(language__isnull=True,
                                      country__isnull=True)
    language = None
    stats_for_language = []

    # We only want to show English-specific anything if English was
    # explicitly passed in the URL.  Otherwise we use the English-language
    # page but without anything specific to only the English contents of
    # the database.
    code = request.LANGUAGE_CODE
    if code and (code != 'en' or request.GET.get('lang') == 'en'):
        try:
            language = Language.objects.get(code=code)
            stats_for_language = CountStats.objects.filter(language=language)
        except Language.DoesNotExist:
            pass

    if (not code) or code not in settings.FRONT_PAGE_LANGUAGES:
        # Make certain that we pick an actual existing page, but
        # leave the language stats matching what was requested.
        code = 'en'
    base_path = 'managed_content/gcd/%s/' % code

    template_vars = {}
    for template in ('front_page_title', 'front_page_main', 'front_page_lower',
                     'fb_feed'):
        template_vars[template] = '%s/%s.html' % (base_path, template)

    template_vars.update({
        'stats': stats,
        'language': language,
        'stats_for_language': stats_for_language,
        'CALENDAR': settings.CALENDAR,
    })
    return render_to_response('gcd/index.html', template_vars,
                              context_instance=RequestContext(request))


class ResponsePaginator(object):
    """
    Uses DiggPaginator from
    http://bitbucket.org/miracle2k/djutils/src/tip/djutils/pagination.py.
    We could reconsider writing our own code.
    """
    def __init__(self, queryset, vars=None, template=None, per_page=100,
                 callback_key=None, callback=None, view=None):
        """
        Either template or view should be set
        """
        if template is None and view is None:
            raise ValueError
        self.template = template
        self.vars = vars and vars or {}
        self.callback_key = callback_key
        self.callback = callback
        self.view = view
        self.p = DiggPaginator(queryset, per_page, body=7, padding=2, tail=1)

    def paginate(self, request):
        page_num = 1
        self.vars['pagination_type'] = 'num'
        redirect = None
        if ('page' in request.GET):
            try:
                page_num = int(request.GET['page'])
                if page_num > self.p.num_pages:
                    redirect = self.p.num_pages
                elif page_num < 1:
                    redirect = 1
            except ValueError:
                if 'alpha_paginator' in self.vars and \
                  request.GET['page'][:2] == 'a_':
                    self.alpha_paginator = self.vars['alpha_paginator']
                    try:
                        alpha_page_num = int(request.GET['page'][2:])
                        if alpha_page_num > self.alpha_paginator.num_pages:
                            redirect = 'a_%d' % self.alpha_paginator.num_pages
                        elif page_num < 1:
                            redirect = 'a_1'
                        else:
                            alpha_page = \
                              self.alpha_paginator.page(alpha_page_num)
                            self.vars['pagination_type'] = 'alpha'
                            self.vars['alpha_page'] = alpha_page
                            issue_count = self.alpha_paginator.number_offset
                            for i in range(1,alpha_page_num):
                                issue_count += \
                                  self.alpha_paginator.page(i).count
                            page_num = int(issue_count/self.p.per_page) + 1
                    except ValueError:
                        redirect = 1
                else:
                    redirect = 1

        if redirect is not None:
            args = request.GET.copy()
            args['page'] = redirect
            return HttpResponseRedirect(quote(request.path.encode('UTF-8')) +
                                        u'?' + args.urlencode())

        page = self.p.page(page_num)
        self.vars['items'] = page.object_list
        self.vars['paginator'] = self.p
        self.vars['page'] = page
        self.vars['page_number'] = page_num

        if self.callback_key is not None:
            self.vars[self.callback_key] = self.callback(page)

        if self.view:
            return self.view()

        return render_to_response(self.template, self.vars,
                                  context_instance=RequestContext(request))


def paginate_response(request, queryset, template, vars, per_page=100,
                      callback_key=None, callback=None):
    return ResponsePaginator(queryset, vars=vars, template=template,
                             per_page=per_page,
                             callback_key=callback_key,
                             callback=callback).paginate(request)
