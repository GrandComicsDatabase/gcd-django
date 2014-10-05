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
    url(r'^collection/add/',
        'apps.mycomics.views.add_collection',
        name='add_collection'),

    url(r'^issue/(?P<issue_id>\d+)/have/$',
     mycomics_views.have_issue, name='have_issue'),
    url(r'^issue/(?P<issue_id>\d+)/want/$',
     mycomics_views.want_issue, name='want_issue'),

    url(r'^mycomics_search/$',
      mycomics_views.mycomics_search, name='mycomics_search'),

)
