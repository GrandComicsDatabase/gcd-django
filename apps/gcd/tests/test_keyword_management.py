"""Management access and rendering checks; no database is required."""

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
    catalog_usage, duplicate_groups, keyword_detail, keyword_duplicates,
    keyword_list, navigation_state, normalized_name)


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

    def render_page(self, template, context):
        return render_to_string(template, {
            'ICON_SET_SYMBOLIC': settings.ICON_SET_SYMBOLIC,
            'ICON_SET': settings.ICON_SET,
            'user': AnonymousUser(),
            **context,
        })

    def test_anonymous_users_are_redirected_to_login(self):
        for view, args in ((keyword_list, ()), (keyword_detail, (1,)),
                           (keyword_duplicates, ())):
            with self.subTest(view=view.__name__):
                response = view(self.request(authenticated=False), *args)
                self.assertEqual(response.status_code, 302)
                self.assertIn('next=', response.url)

    def test_authenticated_user_without_tag_permissions_can_browse(self):
        module = 'apps.gcd.views.keyword_management'
        with patch(module + '.Tag.objects') as tags, \
                patch(module + '.render', return_value=HttpResponse()):
            annotated = tags.all.return_value.annotate.return_value
            annotated.order_by.return_value = []
            response = keyword_list(self.request(permitted=False))
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
        html = self.render_page('gcd/keywords/manage.html', {
            'page_obj': Paginator([keyword], 50).get_page(1),
            'query': '', 'usage': '',
        })
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn(reverse('keyword_manage_detail', args=[12]), html)

    def test_pagination_keeps_search_and_usage_filter(self):
        html = self.render_page('gcd/keywords/manage.html', {
            'page_obj': Paginator([], 50).get_page(1),
            'query': 'London', 'usage': 'unused',
        })
        self.assertIn('No keywords match these filters.', html)
        self.assertIn('value="London"', html)

        page = Paginator([SimpleNamespace(pk=n, name='London', usage_count=0)
                          for n in range(51)], 50).get_page(1)
        html = self.render_page('gcd/keywords/manage.html', {
            'page_obj': page, 'query': 'London & UK', 'usage': 'unused',
        })
        self.assertIn('q=London%20%26%20UK&amp;usage=unused&amp;page=2', html)

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
        self.assertNotEqual(normalized_name('Caf\u00e9'), normalized_name('Cafe'))
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

    def test_sort_is_allowlisted_and_deterministic(self):
        module = 'apps.gcd.views.keyword_management'
        for sort, expected in (('-usage', ('-usage_count', 'name', 'pk')),
                               ('invalid', ('name', 'pk'))):
            with self.subTest(sort=sort), patch(module + '.Tag.objects') as tags, \
                    patch(module + '.render', return_value=HttpResponse()):
                annotated = tags.all.return_value.annotate.return_value
                annotated.order_by.return_value = []
                request = self.request()
                request.GET = self.factory.get('/', {'sort': sort}).GET
                keyword_list(request)
                annotated.order_by.assert_called_once_with(*expected)

    def test_duplicate_template_links_to_ids_and_preserves_return_state(self):
        page = Paginator([{'key': 'london', 'members': [
            {'pk': 12, 'name': 'London', 'usage_count': 2},
            {'pk': 13, 'name': 'LONDON', 'usage_count': 0},
        ]}], 20).get_page(1)
        html = self.render_page('gcd/keywords/duplicates.html', {
            'page_obj': page, 'query': 'London',
            'detail_query': 'q=London&origin=duplicates&page=2',
        })
        self.assertIn('/keywords/manage/12/?q=London&amp;origin=duplicates', html)
        self.assertIn('/keywords/manage/13/?q=London&amp;origin=duplicates', html)
        self.assertIn('LONDON', html)
        self.assertIn('href="/static/css/keyword-manager.css"', html)
        self.assertIn('<main class="kw-manager">', html)
        self.assertIn('class="kw-filters"', html)
        self.assertIn('class="kw-duplicate-group"', html)

    def test_missing_and_deleted_objects_do_not_expose_labels_or_links(self):
        for obj in (None, SimpleNamespace(deleted=True)):
            with self.subTest(obj=obj):
                item = SimpleNamespace(
                    content_object=obj,
                    content_type=SimpleNamespace(model='story'))
                self.assertEqual(catalog_usage(item), {
                    'label': 'Unavailable object', 'url': None, 'type': 'story',
                })

    def test_catalog_object_without_url_is_still_displayed(self):
        item = SimpleNamespace(content_object='Catalog object',
                               content_type=SimpleNamespace(model='story'))
        self.assertEqual(catalog_usage(item), {
            'label': 'Catalog object', 'url': None, 'type': 'story',
        })

    def test_duplicate_counts_are_limited_to_the_current_page(self):
        module = 'apps.gcd.views.keyword_management'
        rows = [(n, f'Place {n // 2}') for n in range(42)]
        with patch(module + '.Tag.objects') as tags, \
                patch(module + '.render', return_value=HttpResponse()) as render:
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
