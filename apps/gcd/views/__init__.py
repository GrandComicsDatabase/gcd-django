"""
Due to uncertainty about how to best structure things and the size of the app,
the models and views were split into multiple individual files instead of
the traditional models.py and views.py files.

This file contains the front page view, plus utilities for working with requests,
responses and errors. 
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

from apps.gcd.models import Error, CountStats, Language

ORDER_ALPHA = "alpha"
ORDER_CHRONO = "chrono"

class ViewTerminationError(Exception):
    """
    Used to end a view from within a helper function.  Takes a Django response
    object in place of a message.  View functions should catch these exceptions
    and simply return the included response.
    """

    def __init__(self, response):
        self.response = response

    def __str__(self):
        return repr(self.response)


def index(request):
    """Generates the front index page."""

    stats = CountStats.objects.filter(language__isnull=True,
                                      country__isnull=True)
    language = None
    # TODO: we want to check here if we actively support the language
    if request.LANGUAGE_CODE != 'en':
        try:
            language = Language.objects.get(code=request.LANGUAGE_CODE)
        except Language.DoesNotExist:
            pass


    if language:
        front_page_content = ("gcd/front_page/front_page_content_%s.html" %
                              language.code)
        stats_for_language = CountStats.objects.filter(language=language)
    else:
        front_page_content = "gcd/front_page/front_page_content.html"
        stats_for_language = None

    vars = { 'stats' : stats, 'language' : language,
             'stats_for_language' : stats_for_language, 
             'front_page_content' : front_page_content,
             'CALENDAR': settings.CALENDAR }
    return render_to_response('gcd/index.html', vars,
                              context_instance=RequestContext(request))
      

class ResponsePaginator(object):
    """
    Uses DiggPaginator from
    http://bitbucket.org/miracle2k/djutils/src/tip/djutils/pagination.py.
    We could reconsider writing our own code.
    """
    def __init__(self, queryset, vars=None, template=None, page_size=100,
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
        self.p = DiggPaginator(queryset, page_size, body=7, padding=2, tail=1)

    def paginate(self, request):
        page_num = 1
        redirect = None
        if ('page' in request.GET):
            try:
                page_num = int(request.GET['page'])
                if page_num > self.p.num_pages:
                    redirect = self.p.num_pages
                elif page_num < 1:
                    redirect = 1
            except ValueError:
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


def paginate_response(request, queryset, template, vars, page_size=100,
                      callback_key=None, callback=None):
    return ResponsePaginator(queryset, vars=vars, template=template,
                             page_size=page_size,
                             callback_key=callback_key,
                             callback=callback).paginate(request)


def render_error(request, error_text, redirect=True, is_safe = False):
    """
    Utility function to render an error page as a response.  Can be
    called to return the page directly as a response or used to
    set up a redirect for which the error message is stored in our
    custom errors table.

    See apps.gcd.models.Error for more details.
    """
    if redirect:
        if error_text != '':
            salt = hashlib.sha1(str(random())).hexdigest()[:5]
            key = hashlib.sha1(salt + error_text.encode('utf-8')).hexdigest()
            Error.objects.create(error_key=key, is_safe=is_safe,
                                  error_text=error_text,)
            return HttpResponseRedirect(
              urlresolvers.reverse('error') +
              u'?error_key=' + key)

        else:
            return HttpResponseRedirect(urlresolvers.reverse('error'))
    else:
        if is_safe:
            error_text = mark_safe(error_text)
        return error_view(request, error_text)


def error_view(request, error_text = ''):
    """
    Looks up a specified error in the GCD's custom errors table,
    and renders a generic error page using that error's text.
    Can be used through a redirect or can be called directly from another view.

    See apps.gcd.models.Error for more details.
    """
    if error_text == '':
        if 'error_key' not in request.GET:
            error_text = 'Unknown error.'
        else:
            key = request.GET['error_key']
            errors = Error.objects.filter(error_key=key)
            if errors.count() == 1:
                error_text = unicode(errors[0])
                if errors[0].is_safe:
                     error_text = mark_safe(error_text)
                errors[0].delete()
            else:
                error_text = 'Unknown error.'
    return render_to_response('gcd/error.html',
                              { 'error_text': error_text },
                              context_instance=RequestContext(request))

