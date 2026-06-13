# -*- coding: utf-8 -*-
from django.db.models import Subquery, OuterRef
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, mixins, generics
from apps.api.serializers import SeriesSerializer, PublisherSerializer, \
                                 IssueSerializer, IssueOnlySerializer, \
                                 SeriesOverviewItemSerializer

from apps.gcd.models import Series, Publisher, Issue
from apps.gcd.models.issue import issues_for_iso_week
from apps.gcd.models.story import Story


class ReadOnlyModelView(mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """
    A viewset that provides default `retrieve()` actions.
    """
    pass


class SeriesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows series to be viewed.
    """
    queryset = Series.objects.filter(deleted=False)
    serializer_class = SeriesSerializer


class SeriesList(generics.ListAPIView):
    """
    API endpoint that allows series to be searched by name.
    """
    serializer_class = SeriesSerializer

    def get_queryset(self):
        name = self.kwargs['name']
        if 'year' in self.kwargs:
            year = self.kwargs['year']

            return Series.objects.filter(name__icontains=name,
                                         year_began=year,
                                         deleted=False)
        return Series.objects.filter(name__icontains=name,
                                     deleted=False)


class IssueViewSet(ReadOnlyModelView):
    """
    API endpoint that allows Issue to be viewed.
    """
    queryset = Issue.objects.filter(deleted=False)
    serializer_class = IssueSerializer


class IssuesList(generics.ListAPIView):
    """
    API endpoint that allows an issue to be searched by series name, number,
    and year.
    """
    serializer_class = IssueOnlySerializer

    def get_queryset(self):
        name = self.kwargs['name']
        number = self.kwargs['number']
        if 'year' in self.kwargs:
            year = self.kwargs['year']

            return Issue.objects.filter(series__name__icontains=name,
                                        number=number,
                                        key_date__startswith=year,
                                        deleted=False)
        return Issue.objects.filter(series__name__icontains=name,
                                    number=number,
                                    deleted=False)


class IssuesByOnSaleWeek(generics.ListAPIView):
    """
    API endpoint that returns all issues on sale in a given ISO week.
    """
    serializer_class = IssueOnlySerializer

    def get_queryset(self):
        qs, _monday, _sunday = issues_for_iso_week(
            int(self.kwargs['year']), int(self.kwargs['week']))
        return qs


class SeriesOverviewList(generics.ListAPIView):
    """
    Returns the cover URL and longest comic story for each non-variant issue
    in a series, mirroring the data shown at /series/<id>/overview/.
    """
    serializer_class = SeriesOverviewItemSerializer

    def get_queryset(self):
        series_id = self.kwargs['series_id']
        series = get_object_or_404(Series, id=series_id, deleted=False)
        return (
            series.active_issues()
            .filter(variant_of=None)
            .annotate(
                longest_story_id=Subquery(
                    Story.objects.filter(
                        issue_id=OuterRef('pk'),
                        type_id=19,
                        deleted=False,
                    ).values('pk').order_by('-page_count', 'sequence_number')[:1]
                )
            )
            .select_related('series__publisher')
        )


class PublisherViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Publishers to be viewed.
    """
    queryset = Publisher.objects.filter(deleted=False)
    serializer_class = PublisherSerializer


# class BrandViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     API endpoint that allows Brands to be viewed.
#     """
#     queryset = Brand.objects.filter(deleted=False)
#     serializer_class = BrandSerializer


# class BrandGroupViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     API endpoint that allows BrandGroup to be viewed.
#     """
#     queryset = BrandGroup.objects.filter(deleted=False)
#     serializer_class = BrandGroupSerializer


# class IndiciaPublisherViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     API endpoint that allows IndiciaPublisher to be viewed.
#     """
#     queryset = IndiciaPublisher.objects.filter(deleted=False)
#     serializer_class = IndiciaPublisherSerializer
