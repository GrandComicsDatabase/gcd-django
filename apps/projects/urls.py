# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic import base as bv

urlpatterns = patterns('',
    url(r'^issues_with_several_covers/$',
        'apps.projects.views.issues_with_several_covers',
        name='issues_with_several_covers'),
    url(r'^story_reprint_inspection/$',
        'apps.projects.views.story_reprint_inspection',
        name='story_reprint_inspection'),
    url('$',
        bv.TemplateView.as_view(template_name='projects/index.html'),
        name='projects_toc'),
)

