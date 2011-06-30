# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template

urlpatterns = patterns('',
    url(r'^imprints_in_use/$', 'apps.projects.views.imprints_in_use',
        name='imprints_in_use'),
    url(r'^series_with_both_notes/$', 'apps.projects.views.series_with_both_notes',
        name='series_with_both_notes'),
    url('$',  direct_to_template,
        { 'template': 'projects/index.html' }, name='projects_toc'),
)

