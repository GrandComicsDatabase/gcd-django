# -*- coding: utf-8 -*-


from django.conf.urls import url

from apps.stats import views


app_name = 'stats'
urlpatterns = [url(r'^download/', views.download, {}, name='download'),]
