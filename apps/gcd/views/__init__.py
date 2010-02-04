import sha
from random import random

from urllib import quote
from django.conf import settings
from django.core import urlresolvers
from django.core.paginator import QuerySetPaginator
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.utils.safestring import mark_safe

from apps.gcd.views.pagination import DiggPaginator

from apps.gcd.models import Error, CountStats

ORDER_ALPHA = "alpha"
ORDER_CHRONO = "chrono"

def index(request):
    """Generates the front index page."""

    style = 'default'
    if 'style' in request.GET:
        style = request.GET['style']

    stats = CountStats.objects.all()

    vars = { 'style' : style, 'stats' : stats }
    return render_to_response('gcd/index.html', vars,
                              context_instance=RequestContext(request))
      

def paginate_response(request, queryset, template, vars, page_size=100,
                      callback_key=None, callback=None):
    """
    Uses DiggPaginator from
    http://bitbucket.org/miracle2k/djutils/src/tip/djutils/pagination.py.
    We could reconsider writing our own code.
    """

    p = DiggPaginator(queryset, page_size, body=5, padding=2)

    page_num = 1
    redirect = None
    if ('page' in request.GET):
        try:
            page_num = int(request.GET['page'])
            if page_num > p.num_pages:
                redirect = p.num_pages
            elif page_num < 1:
                redirect = 1
        except ValueError:
            redirect = 1

    if redirect is not None:
        args = request.GET.copy()
        args['page'] = redirect
        return HttpResponseRedirect(quote(request.path.encode('UTF-8')) +
                                    u'?' + args.urlencode())

    page = p.page(page_num)

    vars['items'] = page.object_list
    vars['paginator'] = p
    vars['page'] = page
    vars['page_number'] = page_num

    if callback_key is not None:
        vars[callback_key] = callback(page)

    return render_to_response(template, vars,
                              context_instance=RequestContext(request))


def render_error(request, error_text, redirect=True, is_safe = False):
    if redirect:
        if error_text != '':
            salt = sha.new(str(random())).hexdigest()[:5]
            key = sha.new(salt + error_text).hexdigest()
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

