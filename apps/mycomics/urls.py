# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from apps.gcd.views import accounts as account_views

urlpatterns = patterns('',
    url(r'^$', 'apps.mycomics.views.index', name='home'),
    url(r'^accounts/login/$', account_views.login,
        {'template_name': 'mycomics/index.html',
        'landing_view': 'collections_list'},
        name='my_login'),
    url(r'^collection/list/$',
        'apps.mycomics.views.collections_list',
        name='collections_list'),
    url(r'^collection/(?P<collection_id>\d+)/',
        'apps.mycomics.views.view_collection',
        name='view_collection'),
    url(r'^collection/add/',
        'apps.mycomics.views.add_collection',
        name='add_collection'),

    url(r'^issue/(?P<issue_id>\d+)/have/$',
     'apps.mycomics.views.have_issue', name='have_issue'),
    url(r'^issue/(?P<issue_id>\d+)/want/$',
     'apps.mycomics.views.want_issue', name='want_issue'),
)
