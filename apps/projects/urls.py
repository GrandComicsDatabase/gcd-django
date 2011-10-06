# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template

urlpatterns = patterns('',
    url(r'^imprints_in_use/$', 'apps.projects.views.imprints_in_use',
        name='imprints_in_use'),
    url(r'^issues_with_several_covers/$', 'apps.projects.views.issues_with_several_covers',
        name='issues_with_several_covers'),
    url(r'^issue_cover_notes/$', 'apps.projects.views.issue_cover_notes',
        name='issue_cover_notes'),
    url(r'^series_with_isbn/$', 'apps.projects.views.series_with_isbn',
        name='series_with_isbn'),
    url('$',  direct_to_template,
        { 'template': 'projects/index.html' }, name='projects_toc'),
)

