# -*- coding: utf-8 -*-
from rest_framework import routers

from apps.api import views

router = routers.DefaultRouter()

router.register(r'series', views.SeriesViewSet)
router.register(r'publisher', views.PublisherViewSet)
router.register(r'brand', views.BrandViewSet)
router.register(r'brand_view', views.BrandGroupViewSet)
router.register(r'issue', views.IssueViewSet)
router.register(r'indicia_publisher', views.IndiciaPublisherViewSet)
