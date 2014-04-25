# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns('', url(r'^$', 'apps.mycomics.views.index', name='home'))