# -*- coding: utf-8 -*-
from django.conf.urls import url
from django.conf import settings
from django.views.generic import base as bv

from apps.projects import views as projects_views

urlpatterns = [
    url(r'^issues_with_several_covers/$',
        projects_views.issues_with_several_covers,
        name='issues_with_several_covers'),
    url(r'^creators_with_no_sort_name/$',
        projects_views.creators_sort_name,
        name='creators_with_no_sort_name'),
    url('$',
        bv.TemplateView.as_view(template_name='projects/index.html'),
        name='projects_toc'),
]
