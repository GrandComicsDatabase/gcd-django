# -*- coding: utf-8 -*-
from django.urls import path
from django.conf import settings
from django.views.generic import base as bv

from apps.projects import views as projects_views

urlpatterns = [
    path('issues_with_several_covers/',
        projects_views.issues_with_several_covers,
        name='issues_with_several_covers'),
    path('series_with_other_country/',
         projects_views.series_with_other_country,
         name='series_with_other_country'),
    path('',
        bv.TemplateView.as_view(template_name='projects/index.html'),
        name='projects_toc'),
]
