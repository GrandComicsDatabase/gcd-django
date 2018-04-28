# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from django.conf.urls import url

from apps.stats import views


urlpatterns = [url(r'^download/', views.download, {}, name='download'),]
