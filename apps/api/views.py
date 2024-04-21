# -*- coding: utf-8 -*-
from rest_framework import viewsets
from apps.api.serializers import SeriesSerializer, PublisherSerializer, \
                                 BrandSerializer, BrandGroupSerializer, \
                                 IssueSerializer, IndiciaPublisherSerializer

from apps.gcd.models import Series, Publisher, Brand, BrandGroup, Issue, \
                            IndiciaPublisher


class SeriesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows series to be viewed.
    """

    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100

    # TODO
    # should we make all series / issues accessible as lists ?
    # or use filters, e.g.
    # https://github.com/AltSchool/dynamic-rest
    # https://www.django-rest-framework.org/api-guide/filtering/
    # def list(self, request):
    #     from rest_framework import status
    #     from rest_framework.response import Response

    #     return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class PublisherViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Publishers to be viewed.
    """

    queryset = Publisher.objects.all()
    serializer_class = PublisherSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Brands to be viewed.
    """

    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class BrandGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows BrandGroup to be viewed.
    """

    queryset = BrandGroup.objects.all()
    serializer_class = BrandGroupSerializer


class IssueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Issue to be viewed.
    """

    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100


class IndiciaPublisherViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows IndiciaPublisher to be viewed.
    """

    queryset = IndiciaPublisher.objects.all()
    serializer_class = IndiciaPublisherSerializer
    paginate_by = 10
    paginate_by_param = 'page_size'
    # set MAX results per page
    max_paginate_by = 100
