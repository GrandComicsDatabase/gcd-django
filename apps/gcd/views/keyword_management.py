"""Read-only keyword list and management using the existing taggit tables."""

from collections import defaultdict
from unicodedata import normalize
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.views.decorators.vary import vary_on_headers
import django_tables2 as tables
from django_tables2 import RequestConfig
from taggit.models import Tag, TaggedItem

from apps.gcd.views.details import TW_SORT_TABLE_TEMPLATE


KEYWORDS_PER_PAGE = 50
DUPLICATE_GROUPS_PER_PAGE = 20
OBJECTS_PER_PAGE = 25
NAVIGATION_PARAMETERS = ('q', 'usage', 'sort', 'page', 'origin')


def normalized_name(name):
    """Compare spellings without changing stored names or removing accents."""
    return normalize('NFC', normalize('NFC', name).strip().casefold())


def duplicate_groups(rows, query=''):
    """Keep complete groups, even when only one spelling matches the query."""
    groups = defaultdict(list)
    query = normalized_name(query)
    for pk, name in rows:
        key = normalized_name(name)
        if query in key:
            groups[key].append({'pk': pk, 'name': name})
    duplicates = [{'key': key, 'members': members}
                  for key, members in groups.items() if len(members) > 1]
    return sorted(duplicates, key=lambda group: group['key'])


def navigation_state(request, **overrides):
    """Carry only known list parameters, never an arbitrary redirect URL."""
    state = {key: request.GET[key] for key in NAVIGATION_PARAMETERS
             if key in request.GET}
    state.update(overrides)
    return urlencode(state)


def catalog_usage(item):
    """Do not expose labels or links for deleted or missing catalog objects."""
    obj = item.content_object
    if obj is None or getattr(obj, 'deleted', False):
        return {'label': 'Unavailable object', 'url': None,
                'type': item.content_type.model}
    get_url = getattr(obj, 'get_absolute_url', None)
    return {'label': str(obj), 'url': get_url() if callable(get_url) else None,
            'type': item.content_type.model}


@require_safe
@never_cache
@login_required
def keyword_duplicates(request):
    query = request.GET.get('q', '').strip()
    # Python normalization deliberately avoids database collation semantics.
    groups = duplicate_groups(
        Tag.objects.order_by('pk').values_list('pk', 'name').iterator(), query)
    page = Paginator(groups, DUPLICATE_GROUPS_PER_PAGE).get_page(
        request.GET.get('page'))
    ids = [member['pk'] for group in page for member in group['members']]
    counts = dict(
        Tag.objects.filter(pk__in=ids)
        .annotate(usage_count=Count('taggit_taggeditem_items'))
        .values_list('pk', 'usage_count')
    )
    for group in page:
        for member in group['members']:
            member['usage_count'] = counts.get(member['pk'], 0)
    return render(request, 'gcd/keywords/duplicates.html', {
        'page_obj': page,
        'query': query,
        'detail_query': navigation_state(request, origin='duplicates',
                                         page=page.number, q=query),
    })


class KeywordTable(tables.Table):
    name = tables.Column(verbose_name='Keyword', order_by=('name', 'pk'))
    usage_count = tables.Column(verbose_name='Usages',
                                order_by=('usage_count', 'name', 'pk'),
                                attrs={'th': {'class': 'text-right'},
                                       'td': {'class': 'text-right'}})

    class Meta:
        template_name = TW_SORT_TABLE_TEMPLATE
        order_by_field = 'sort'
        attrs = {'class': 'w-full'}
        empty_text = 'No keywords match these filters.'

    def __init__(self, *args, detail_query=None, **kwargs):
        self.detail_query = detail_query
        super().__init__(*args, **kwargs)
        self.no_export = True

    def render_name(self, record):
        if self.detail_query is None:
            return format_html('<a href="{}">{}</a>', reverse(
                'show_keyword', kwargs={'keyword': record.name}), record.name)
        url = '%s?%s' % (reverse('keyword_manage_detail', args=[record.pk]),
                         self.detail_query)
        return format_html(
            '<a id="keyword-{}" href="{}" hx-get="{}" hx-target="#keyword-detail"'
            ' hx-push-url="false" hx-sync="#keyword-detail:replace"'
            ' aria-controls="keyword-detail" aria-expanded="false">{}</a>',
            record.pk, url, url, record.name)


@require_safe
@never_cache
@vary_on_headers('HX-Request', 'HX-History-Restore-Request')
def keyword_list(request, keyword=''):
    """Public keyword list; signed-in users also see unused keywords."""
    query = request.GET.get('q', keyword).strip()
    keywords = Tag.objects.all()
    if query:
        keywords = keywords.filter(name__icontains=query)
    # Only public catalog objects count, never private collection items.
    keywords = keywords.annotate(usage_count=Count(
        'taggit_taggeditem_items',
        filter=Q(taggit_taggeditem_items__content_type__app_label='gcd')))
    usage = request.GET.get('usage', '')
    if not request.user.is_authenticated:
        usage = 'used'
    if usage == 'unused':
        keywords = keywords.filter(usage_count=0)
    elif usage == 'used':
        keywords = keywords.filter(usage_count__gt=0)
    else:
        usage = ''
    detail_query = None
    if request.user.is_authenticated:
        detail_query = navigation_state(request, origin='list', q=query,
                                        usage=usage)
    table = KeywordTable(keywords, detail_query=detail_query,
                         order_by=request.GET.get('sort') or '-usage_count')
    RequestConfig(request, paginate={'per_page': KEYWORDS_PER_PAGE}).configure(
        table)
    template = ('gcd/keywords/partials/results.html' if inline_request(request)
                else 'gcd/keywords/manage.html')
    return render(request, template, {
        'table': table,
        'page_obj': table.page,
        'query': query,
        'usage': usage,
    })


@require_safe
@never_cache
@login_required
@vary_on_headers('HX-Request', 'HX-History-Restore-Request')
def keyword_detail(request, pk):
    keyword = get_object_or_404(Tag, pk=pk)
    usage_groups = list(
        TaggedItem.objects.filter(tag_id=keyword.pk)
        .values('content_type__app_label', 'content_type__model')
        .annotate(total=Count('pk'))
        .order_by('content_type__app_label', 'content_type__model')
    )
    # Collection objects may be private. Only link to public catalog objects.
    associations = TaggedItem.objects.filter(
        tag_id=keyword.pk, content_type__app_label='gcd').order_by('pk')
    objects_page = Paginator(associations, OBJECTS_PER_PAGE).get_page(
        request.GET.get('objects_page'))
    usages = [catalog_usage(item) for item in
              objects_page.object_list.prefetch_related(
                  'content_type', 'content_object')]
    origin = ('keyword_manage_duplicates'
              if request.GET.get('origin') == 'duplicates'
              else 'keyword_by_name')
    state = navigation_state(request)
    inline = inline_request(request)
    template = ('gcd/keywords/partials/detail.html' if inline
                else 'gcd/keywords/detail.html')
    return render(request, template, {
        'detail_inline': inline,
        'keyword': keyword,
        'usage_groups': usage_groups,
        'usage_count': sum(group['total'] for group in usage_groups),
        'back_url': reverse(origin) + ('?' + state if state else ''),
        'navigation_query': state,
        'objects_page': objects_page,
        'usages': usages,
    })


def inline_request(request):
    """History cache misses must receive a complete navigable document."""
    return (request.headers.get('HX-Request') == 'true' and
            request.headers.get('HX-History-Restore-Request') != 'true')
