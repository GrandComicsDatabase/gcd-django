# -*- coding: utf-8 -*-
from django.urls import path
from rest_framework import routers

from apps.api import views

router = routers.DefaultRouter()

router.register(r'issue', views.IssueViewSet)
router.register(r'series', views.SeriesViewSet)
router.register(r'publisher', views.PublisherViewSet)
# router.register(r'brand', views.BrandViewSet)
# router.register(r'brand_view', views.BrandGroupViewSet)
# router.register(r'indicia_publisher', views.IndiciaPublisherViewSet)

urlpatterns = [
    path('series/name/<path:name>/issue/<path:number>/year/<str:year>/',
         views.IssuesList.as_view()),
    path('series/name/<path:name>/issue/<path:number>/',
         views.IssuesList.as_view()),
    path('series/name/<path:name>/year/<int:year>/',
         views.SeriesList.as_view()),
    path('series/name/<path:name>/', views.SeriesList.as_view()),
]
