# -*- coding: utf-8 -*-


from django.urls import path, re_path

from apps.stats import views


app_name = 'stats'
urlpatterns = [re_path(r'^download/', views.download, {}, name='download'),
               path('countries/', views.countries_in_use),
]
