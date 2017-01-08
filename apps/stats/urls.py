# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from django.conf.urls import patterns, url

from apps.stats import views


urlpatterns = patterns('',
    url(r'^download/', views.download, {}, name='download'),
)
