"""
Due to uncertainty about how to best structure things and the size of the app,
the models and views were split into multiple individual files instead of
the traditional models.py and views.py files.

This file contains the front page view, plus utilities for working with
requests, responses and errors.
"""

from datetime import datetime

from django.conf import settings
from django.shortcuts import render
from django.db.models import Count

from .pagination import DiggPaginator
from .alpha_pagination import AlphaPaginator

from apps.stddata.models import Language
from apps.stats.models import CountStats
from apps.gcd.models import Creator

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

    today = datetime.today()
    day = '%0.2d' % (today).day
    month = '%0.2d' % (today).month
    creators = Creator.objects.filter(birth_date__day__lte=day,
                                      birth_date__month=month,
                                      deleted=False)\
                              .exclude(birth_date__day='')\
                              .exclude(birth_date__month__lte='')\
                              .exclude(bio='').order_by('-birth_date__month',
                                                        '-birth_date__day',
                                                        'sort_name')[:100]
    creators = list(creators.values_list('id', flat=True))
    if len(creators) < 100:
        creators_2 = Creator.objects.filter(birth_date__month__lt=month,
                                            deleted=False)\
                                    .exclude(birth_date__day='')\
                                    .exclude(birth_date__month__lte='')\
                                    .exclude(bio='')\
                                    .order_by('-birth_date__month',
                                              '-birth_date__day',
                                              'sort_name')[:100]
        creators.extend(list(creators_2.values_list('id', flat=True)))
    creators = Creator.objects.filter(id__in=creators)\
                      .annotate(issue_count=Count(
                        'creator_names__storycredit__story__issue',
                        distinct=True))\
                      .filter(issue_count__gt=10)\
                      .order_by('-birth_date__month',
                                '-birth_date__day',
                                'sort_name').select_related('birth_date')
    creators_count = len(creators)
    creator_last = creators[10]
    last_listed = 10
    for i in range(11, creators_count):
        if creators[i].birth_date.month != creator_last.birth_date.month or \
           creators[i].birth_date.day != creator_last.birth_date.day:
            last_listed = i
            break

    template_vars.update({
        'stats': stats,
        'language': language,
        'stats_for_language': stats_for_language,
        'creators': creators[:last_listed],
    })
    return render(request, 'gcd/tw_index.html', template_vars)


class ResponsePaginator(object):
    """
    Uses DiggPaginator from
    http://bitbucket.org/miracle2k/djutils/src/tip/djutils/pagination.py.
    We could reconsider writing our own code.
    """
    def __init__(self, queryset, vars=None, per_page=100, alpha=False):
        self.vars = vars or {}
        self.p = DiggPaginator(queryset, per_page, body=7, padding=2, tail=1)
        if alpha:
            alpha_paginator = AlphaPaginator(queryset, per_page=per_page)
            self.vars['alpha_paginator'] = alpha_paginator

    def paginate(self, request):
        page_num = 1
        self.vars['pagination_type'] = 'num'
        if ('page' in request.GET):
            try:
                page_num = int(request.GET['page'])
                if page_num > self.p.num_pages:
                    page_num = self.p.num_pages
                elif page_num < 1:
                    page_num = 1
            except ValueError:
                if 'alpha_paginator' in self.vars and \
                  request.GET['page'][:2] == 'a_':
                    self.alpha_paginator = self.vars['alpha_paginator']
                    try:
                        alpha_page_num = int(request.GET['page'][2:])
                        if alpha_page_num > self.alpha_paginator.num_pages:
                            alpha_page_num = self.alpha_paginator.num_pages
                        elif alpha_page_num < 1:
                            alpha_page_num = 1
                        alpha_page = self.alpha_paginator.page(alpha_page_num)
                        self.vars['pagination_type'] = 'alpha'
                        self.vars['alpha_page'] = alpha_page
                        issue_count = self.alpha_paginator.number_offset
                        for i in range(1, alpha_page_num):
                            issue_count += \
                              self.alpha_paginator.page(i).count
                        page_num = int(issue_count/self.p.per_page) + 1
                    except ValueError:
                        page_num = 1
                else:
                    page_num = 1

        page = self.p.page(page_num)
        self.vars['page'] = page
        self.vars['items'] = page.object_list
        return page


def paginate_response(request, queryset, template, vars, per_page=100,
                      callback_key=None, callback=None, alpha=False):
    paginator = ResponsePaginator(queryset, vars=vars, per_page=per_page,
                                  alpha=alpha)
    page = paginator.paginate(request)

    if callback_key is not None:
        vars[callback_key] = callback(page)

    return render(request, template, vars)
