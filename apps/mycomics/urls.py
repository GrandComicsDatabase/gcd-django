# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from apps.gcd.views import accounts as account_views
from apps.mycomics import views as mycomics_views

urlpatterns = patterns('',
    url(r'^$', 'apps.mycomics.views.index', name='home'),
    url(r'^accounts/login/$', account_views.login,
        {'template_name': 'mycomics/index.html',
        'landing_view': 'collections_list'},
        name='my_login'),
    url(r'^collection/list/$',
        mycomics_views.collections_list,
        name='collections_list'),
    url(r'^collection/(?P<collection_id>\d+)/',
        mycomics_views.view_collection,
        name='view_collection'),
    url(r'^collection/add/$',
        'apps.mycomics.views.edit_collection',
        name='add_collection'),
    url(r'^collection/edit/(?P<collection_id>\d+)/$',
        'apps.mycomics.views.edit_collection',
        name='edit_collection'),

    url(r'^collection/delete/(?:(?P<collection_id>\d+)?)$',
        'apps.mycomics.views.delete_collection',
        name='delete_collection'),

    url(r'^series/(?P<series_id>\d+)/add_to_collection/$',
     mycomics_views.add_series_issues_to_collection, name='my_series_issues'),
    url(r'^issue/(?P<issue_id>\d+)/add_to_collection/$',
     mycomics_views.add_single_issue_to_collection, name='my_issue'),

    url(r'^mycomics_search/$',
      mycomics_views.mycomics_search, name='mycomics_search'),

)
