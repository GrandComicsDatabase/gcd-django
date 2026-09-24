"""Read-only keyword management using the existing taggit tables."""

from collections import defaultdict
from unicodedata import normalize
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from taggit.models import Tag, TaggedItem


SORTS = {
    'name': ('name', 'pk'),
    '-name': ('-name', 'pk'),
    'usage': ('usage_count', 'name', 'pk'),
    '-usage': ('-usage_count', 'name', 'pk'),
}
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


@require_safe
@never_cache
@login_required
def keyword_list(request):
    query = request.GET.get('q', '').strip()
    usage = request.GET.get('usage', '')
    keywords = Tag.objects.all()
    if query:
        keywords = keywords.filter(name__icontains=query)
    keywords = keywords.annotate(
        usage_count=Count('taggit_taggeditem_items'))
    if usage == 'unused':
        keywords = keywords.filter(usage_count=0)
    elif usage == 'used':
        keywords = keywords.filter(usage_count__gt=0)
    else:
        usage = ''
    sort = request.GET.get('sort', 'name')
    if sort not in SORTS:
        sort = 'name'
    page = Paginator(
        keywords.order_by(*SORTS[sort]), KEYWORDS_PER_PAGE
    ).get_page(request.GET.get('page'))
    return render(request, 'gcd/keywords/manage.html', {
        'page_obj': page,
        'query': query,
        'usage': usage,
        'sort': sort,
        'detail_query': navigation_state(request, origin='list',
                                         page=page.number, sort=sort,
                                         q=query, usage=usage),
    })


@require_safe
@never_cache
@login_required
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
              else 'keyword_manage')
    state = navigation_state(request)
    return render(request, 'gcd/keywords/detail.html', {
        'keyword': keyword,
        'usage_groups': usage_groups,
        'usage_count': sum(group['total'] for group in usage_groups),
        'back_url': reverse(origin) + ('?' + state if state else ''),
        'navigation_query': state,
        'objects_page': objects_page,
        'usages': usages,
    })
