# -*- coding: utf-8 -*-
from rest_framework import viewsets
from apps.api.serializers import SeriesSerializer, PublisherSerializer, \
                                 BrandSerializer, BrandGroupSerializer, \
                                 IssueSerializer, IndiciaPublisherSerializer

from apps.gcd.models import Series, Publisher, Brand, BrandGroup, Issue,\
                            IndiciaPublisher


class SeriesViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows series to be viewed or edited.
    """

    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class PublisherViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Publishers to be viewed or edited.
    """

    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class BrandViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Brands to be viewed or edited.
    """

    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class BrandGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows BrandGroup to be viewed or edited.
    """

    queryset = BrandGroup.objects.all()
    serializer_class = BrandGroupSerializer


class IssueViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Issue to be viewed or edited.
    """

    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class IndiciaPublisherViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows IndiciaPublisher to be viewed or edited.
    """

    queryset = IndiciaPublisher.objects.all()
    serializer_class = IndiciaPublisherSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100
