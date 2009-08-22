from django.conf import settings
from django.core.paginator import QuerySetPaginator
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response

ORDER_ALPHA = "alpha"
ORDER_CHRONO = "chrono"

def index(request):
    """Generates the front index page."""

    style = 'default'
    if 'style' in request.GET:
        style = request.GET['style']

    vars = { 'style' : style }
    return render_to_response('gcd/index.html', vars,
                              context_instance=RequestContext(request))
      

PAGE_DELTA = 2
def paginate_response(request, queryset, template, vars, page_size=100,
                      callback_key=None, callback=None):
    """
    Quick hack to implement direct page links, needs revisiting later
    or we should reconsider using another library such as DiggPaginator.
    """
    p = QuerySetPaginator(queryset, page_size)

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
        return HttpResponseRedirect(request.path + '?' + args.urlencode())

    page = p.page(page_num)

    page_min = page_num - PAGE_DELTA
    low_page_range = ()
    if page_min <= 1 + PAGE_DELTA:
        page_min = 1
    else:
        low_page_range = range(1, PAGE_DELTA +1)

    page_max = page_num + PAGE_DELTA
    high_page_range = ()
    if page_max >= p.num_pages - PAGE_DELTA:
        page_max = p.num_pages
    else:
        high_page_range = range(p.num_pages - PAGE_DELTA +1,
                                p.num_pages + 1)
    vars['items'] = page.object_list
    vars['paginator'] = p
    vars['page'] = page
    vars['page_number'] = page_num
    vars['ranges'] = { 'low': low_page_range,
                       'current': range(page_min, page_max + 1),
                       'current_max': page_max,
                       'high': high_page_range,
                     }

    if callback_key is not None:
        vars[callback_key] = callback(page)

    return render_to_response(template, vars,
                              context_instance=RequestContext(request))

