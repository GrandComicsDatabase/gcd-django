# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from apps.gcd.views import accounts as account_views

urlpatterns = patterns('', url(r'^$', 'apps.mycomics.views.index', name='home'),
                           url(r'^accounts/login/$', account_views.login,
                               {'template_name': 'mycomics/index.html',
                                'landing_view': 'collections'},
                               name='my_login'),
                           url(r'^collections/$',
                               'apps.mycomics.views.collections',
                               name='collections'),
                           url(r'^collection/(?P<collection_id>\d+)/$',
                               'apps.mycomics.views.collection',
                               name='collection'),
                           )
