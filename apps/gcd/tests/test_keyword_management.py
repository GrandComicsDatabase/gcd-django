"""Keyword list and management checks; no database is required."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.gcd.views.keyword_management import (
    KeywordTable, catalog_usage, duplicate_groups, keyword_detail,
    keyword_duplicates, keyword_list, navigation_state, normalized_name)

MODULE = 'apps.gcd.views.keyword_management'


@contextmanager
def list_view_patches():
    """Run keyword_list without a database: the table only gets configured."""
    with patch(MODULE + '.Tag.objects') as tags, \
            patch(MODULE + '.KeywordTable') as table, \
            patch(MODULE + '.RequestConfig'), \
            patch(MODULE + '.render', return_value=HttpResponse()) as render:
        yield SimpleNamespace(tags=tags, table=table, render=render)


@override_settings(ALLOWED_HOSTS=['testserver'])
class KeywordManagementTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, method='get', permitted=True, authenticated=True):
        request = getattr(self.factory, method)('/keywords/manage/')
        request.user = SimpleNamespace(
            is_authenticated=authenticated,
            has_perms=lambda permissions: permitted)
        return request

    def render_page(self, template, context, request=None):
        return render_to_string(template, {
            'ICON_SET_SYMBOLIC': settings.ICON_SET_SYMBOLIC,
            'ICON_SET': settings.ICON_SET,
            'user': AnonymousUser(),
            **context,
        }, request=request)

    def render_list(self, keywords, query='', usage='', detail_query='',
                    params=None):
        request = self.factory.get('/keyword/name/', params or {})
        request.user = AnonymousUser()
        table = KeywordTable(keywords, detail_query=detail_query)
        table.paginate(page=request.GET.get('page', 1), per_page=50)
        return self.render_page('gcd/keywords/manage.html', {
            'table': table, 'page_obj': table.page,
            'query': query, 'usage': usage,
        }, request)

    def test_anonymous_users_are_redirected_to_login(self):
        for view, args in ((keyword_detail, (1,)), (keyword_duplicates, ())):
            with self.subTest(view=view.__name__):
                response = view(self.request(authenticated=False), *args)
                self.assertEqual(response.status_code, 302)
                self.assertIn('next=', response.url)

    def test_anonymous_users_see_used_keywords_with_public_links(self):
        with list_view_patches() as view:
            request = self.request(authenticated=False)
            request.GET = self.factory.get('/', {'usage': 'unused'}).GET
            response = keyword_list(request)
            annotated = view.tags.all.return_value.annotate.return_value
            annotated.filter.assert_called_once_with(usage_count__gt=0)
            self.assertIsNone(view.table.call_args.kwargs['detail_query'])
            self.assertEqual(view.render.call_args.args[2]['usage'], 'used')
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_without_tag_permissions_can_browse(self):
        with list_view_patches() as view:
            response = keyword_list(self.request(permitted=False))
            self.assertEqual(view.table.call_args.kwargs['detail_query'],
                             'origin=list&q=&usage=')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])

    def test_authenticated_user_without_tag_permissions_can_view_detail(self):
        module = 'apps.gcd.views.keyword_management'
        with patch(module + '.get_object_or_404',
                   return_value=SimpleNamespace(pk=12)), \
                patch(module + '.TaggedItem.objects') as items, \
                patch(module + '.render', return_value=HttpResponse()):
            groups = items.filter.return_value.values.return_value
            groups.annotate.return_value.order_by.return_value = []
            associations = items.filter.return_value.order_by.return_value
            associations.count.return_value = 0
            response = keyword_detail(self.request(permitted=False), 12)
            items.filter.assert_any_call(tag_id=12)
            items.filter.assert_any_call(tag_id=12,
                                         content_type__app_label='gcd')
        self.assertEqual(response.status_code, 200)

    def test_write_methods_are_rejected_without_database_access(self):
        for method in ('post', 'put', 'patch', 'delete'):
            for view, args in ((keyword_list, ()), (keyword_detail, (1,)),
                               (keyword_duplicates, ())):
                with self.subTest(method=method, view=view.__name__):
                    response = view(self.request(method), *args)
                    self.assertEqual(response.status_code, 405)

    def test_missing_keyword_returns_404(self):
        with patch('apps.gcd.views.keyword_management.get_object_or_404',
                   side_effect=Http404):
            with self.assertRaises(Http404):
                keyword_detail(self.request(), 123)

    def test_list_escapes_names_and_links_by_id(self):
        keyword = SimpleNamespace(pk=12, name='<script>alert(1)</script>',
                                  usage_count=0)
        html = self.render_list([keyword])
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn(reverse('keyword_manage_detail', args=[12]), html)

    def test_public_list_links_to_the_keyword_page(self):
        html = self.render_list(
            [SimpleNamespace(pk=12, name='London', usage_count=3)],
            detail_query=None)
        self.assertIn('href="%s"' % reverse(
            'show_keyword', kwargs={'keyword': 'London'}), html)
        self.assertNotIn(reverse('keyword_manage_detail', args=[12]), html)

    def test_pagination_keeps_search_and_usage_filter(self):
        html = self.render_list([], query='London', usage='unused')
        self.assertIn('No keywords match these filters.', html)
        self.assertIn('value="London"', html)

        html = self.render_list(
            [SimpleNamespace(pk=n, name='London', usage_count=0)
             for n in range(51)], query='London & UK', usage='unused',
            params={'q': 'London & UK', 'usage': 'unused', 'sort': 'name'})
        self.assertIn('href="?q=London+%26+UK&amp;usage=unused&amp;sort=name'
                      '&amp;page=2"', html)

    def test_unused_keyword_detail_renders_without_edit_form(self):
        html = self.render_page('gcd/keywords/detail.html', {
            'keyword': SimpleNamespace(pk=12, name='London', slug='london'),
            'usage_groups': [], 'usage_count': 0,
        })
        self.assertIn('This keyword is not currently used.', html)
        self.assertNotIn('method="post"', html.lower())

    def test_duplicate_groups_preserve_all_variants(self):
        rows = [(1, 'London'), (2, 'LONDON'), (3, ' london '),
                (4, 'Londra'), (5, 'Paris')]
        groups = duplicate_groups(rows, 'LoNDoN')
        self.assertEqual(len(groups), 1)
        self.assertEqual([member['pk'] for member in groups[0]['members']],
                         [1, 2, 3])
        self.assertEqual(duplicate_groups(rows, 'Londra'), [])

    def test_normalization_handles_unicode_without_losing_distinctions(self):
        self.assertEqual(normalized_name(' E\u0301cole '),
                         normalized_name('\u00c9COLE'))
        self.assertEqual(normalized_name('Stra\u00dfe'),
                         normalized_name('STRASSE'))
        self.assertNotEqual(normalized_name('Caf\u00e9'),
                            normalized_name('Cafe'))
        self.assertNotEqual(normalized_name('New  York'),
                            normalized_name('New York'))
        self.assertNotEqual(normalized_name('U.K.'), normalized_name('UK'))

    def test_navigation_preserves_list_state_only(self):
        request = self.factory.get('/', {
            'q': 'London & UK', 'usage': 'unused', 'sort': '-usage',
            'page': '3', 'origin': 'duplicates', 'objects_page': '2',
            'next': 'https://example.com',
        })
        state = parse_qs(navigation_state(request))
        self.assertEqual(state, {
            'q': ['London & UK'], 'usage': ['unused'], 'sort': ['-usage'],
            'page': ['3'], 'origin': ['duplicates'],
        })

    def test_list_sorts_by_table_columns_with_most_used_first(self):
        for params, expected in (({}, '-usage_count'),
                                 ({'sort': 'name'}, 'name')):
            with self.subTest(params=params), list_view_patches() as view:
                request = self.request()
                request.GET = self.factory.get('/', params).GET
                keyword_list(request)
                self.assertEqual(view.table.call_args.kwargs['order_by'],
                                 expected)
        table = KeywordTable([], order_by='invalid')
        self.assertEqual(list(table.order_by), [])
        self.assertEqual(KeywordTable.base_columns['usage_count'].order_by,
                         ('usage_count', 'name', 'pk'))

    def test_duplicate_template_links_to_ids_and_preserves_return_state(self):
        page = Paginator([{'key': 'london', 'members': [
            {'pk': 12, 'name': 'London', 'usage_count': 2},
            {'pk': 13, 'name': 'LONDON', 'usage_count': 0},
        ]}], 20).get_page(1)
        html = self.render_page('gcd/keywords/duplicates.html', {
            'page_obj': page, 'query': 'London',
            'detail_query': 'q=London&origin=duplicates&page=2',
        })
        self.assertIn('/keywords/manage/12/?q=London&amp;origin=duplicates',
                      html)
        self.assertIn('/keywords/manage/13/?q=London&amp;origin=duplicates',
                      html)
        self.assertIn('LONDON', html)
        self.assertNotIn('keyword-manager.css', html)
        self.assertNotIn('kw-', html)
        self.assertIn('How matching works', html)
        self.assertIn('Search groups', html)

    def test_missing_and_deleted_objects_do_not_expose_labels_or_links(self):
        for obj in (None, SimpleNamespace(deleted=True)):
            with self.subTest(obj=obj):
                item = SimpleNamespace(
                    content_object=obj,
                    content_type=SimpleNamespace(model='story'))
                self.assertEqual(catalog_usage(item), {
                    'label': 'Unavailable object', 'url': None,
                    'type': 'story',
                })

    def test_catalog_object_without_url_is_still_displayed(self):
        item = SimpleNamespace(content_object='Catalog object',
                               content_type=SimpleNamespace(model='story'))
        self.assertEqual(catalog_usage(item), {
            'label': 'Catalog object', 'url': None, 'type': 'story',
        })

    def test_live_search_returns_fragment_but_history_returns_full_page(self):
        for inline, restore, template in (
                (False, False, 'gcd/keywords/manage.html'),
                (True, False, 'gcd/keywords/partials/results.html'),
                (True, True, 'gcd/keywords/manage.html')):
            with self.subTest(inline=inline, restore=restore), \
                    list_view_patches() as view:
                render = view.render
                request = self.request()
                if inline:
                    request.META['HTTP_HX_REQUEST'] = 'true'
                if restore:
                    request.META['HTTP_HX_HISTORY_RESTORE_REQUEST'] = 'true'
                response = keyword_list(request)
                self.assertEqual(render.call_args.args[1], template)
                self.assertIn('HX-Request', response['Vary'])
                self.assertIn('HX-History-Restore-Request', response['Vary'])
                self.assertIn('no-store', response['Cache-Control'])

    def test_inline_details_keep_catalog_privacy_and_history_fallback(self):
        module = 'apps.gcd.views.keyword_management'
        for restore, template in (
                (False, 'gcd/keywords/partials/detail.html'),
                (True, 'gcd/keywords/detail.html')):
            with self.subTest(restore=restore), \
                    patch(module + '.get_object_or_404',
                          return_value=SimpleNamespace(pk=12)), \
                    patch(module + '.TaggedItem.objects') as items, \
                    patch(module + '.render',
                          return_value=HttpResponse()) as render:
                groups = items.filter.return_value.values.return_value
                groups.annotate.return_value.order_by.return_value = []
                associations = items.filter.return_value.order_by.return_value
                associations.count.return_value = 0
                request = self.request()
                request.META['HTTP_HX_REQUEST'] = 'true'
                if restore:
                    request.META['HTTP_HX_HISTORY_RESTORE_REQUEST'] = 'true'
                response = keyword_detail(request, 12)
                self.assertEqual(render.call_args.args[1], template)
                items.filter.assert_any_call(tag_id=12,
                                             content_type__app_label='gcd')
                self.assertIn('HX-Request', response['Vary'])

    def test_inline_detail_pagination_uses_detail_url_and_escapes_name(self):
        html = self.render_page('gcd/keywords/partials/detail.html', {
            'keyword': SimpleNamespace(pk=12, name='<script>x</script>',
                                       slug='example'),
            'usage_groups': [], 'usage_count': 26, 'detail_inline': True,
            'objects_page': Paginator(list(range(26)), 25).get_page(1),
            'navigation_query': 'q=London&page=3', 'usages': [],
        })
        self.assertIn('&lt;script&gt;x&lt;/script&gt;', html)
        self.assertNotIn('<script>x</script>', html)
        self.assertIn('/keywords/manage/12/?q=London&amp;page=3'
                      '&amp;objects_page=2', html)
        self.assertIn('hx-target="#keyword-detail"', html)
        self.assertNotIn('<html', html)

    def test_live_search_keeps_full_page_links_and_tailwind(self):
        html = self.render_list(
            [SimpleNamespace(pk=12, name='London', usage_count=0)])
        self.assertIn('js/htmx_2_0_8.min.js', html)
        self.assertIn('js/keyword_filters.js', html)
        self.assertIn('hx-target="#keyword-results"', html)
        self.assertIn('href="/keywords/manage/12/?"', html)
        self.assertIn('type="submit" class="btn-blue-editing"', html)
        self.assertIn('bg-blue-100', html)
        self.assertNotIn('keyword-manager.css', html)

    def test_duplicate_counts_are_limited_to_the_current_page(self):
        module = 'apps.gcd.views.keyword_management'
        rows = [(n, f'Place {n // 2}') for n in range(42)]
        with patch(module + '.Tag.objects') as tags, \
                patch(module + '.render',
                      return_value=HttpResponse()) as render:
            names = tags.order_by.return_value.values_list.return_value
            names.iterator.return_value = iter(rows)
            counted = tags.filter.return_value.annotate.return_value
            counted.values_list.return_value = []
            response = keyword_duplicates(self.request())
            page = render.call_args.args[2]['page_obj']
            ids = tags.filter.call_args.kwargs['pk__in']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(page.paginator.count, 21)
        self.assertEqual(len(page), 20)
        self.assertEqual(len(ids), 40)
