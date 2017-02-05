# -*- coding: utf-8 -*-
from rest_framework import serializers
from apps.gcd.models import Series, Publisher, Brand, BrandGroup, Issue, \
                            IndiciaPublisher


class SeriesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Series
        fields = ('url', 'id', 'name', 'binding', 'color', 'created',
                  'deleted', 'dimensions', 'format', 'has_barcode',
                  'has_gallery', 'has_indicia_frequency', 'has_isbn',
                  'has_issue_title', 'has_rating', 'publisher')


class PublisherSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Publisher
        fields = ('url', 'name', 'id', 'brand_count', 'series_count')


class BrandSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Brand
        fields = ('url', 'name', 'id', 'group', 'year_began', 'year_ended',
                  'issue_count')


class BrandGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BrandGroup
        fields = ('url', 'name')


class IssueSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Issue
        fields = ('url', 'brand', 'id', 'series', 'title',
                  'first_issue_series_set', 'rating', 'indicia_publisher')


class IndiciaPublisherSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = IndiciaPublisher
        fields = ('url', 'id', 'name', 'issue_count', 'parent')
