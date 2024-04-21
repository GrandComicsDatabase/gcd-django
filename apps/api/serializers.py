# -*- coding: utf-8 -*-
from rest_framework import serializers
from apps.gcd.models import Series, Publisher, Brand, BrandGroup, Issue, \
                            IndiciaPublisher


class IssueSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Issue
        exclude = ['created', 'is_indexed', 'indicia_printer']

    # TODO
    # how to embed stories
    # a) credits as links and text, or text only ?
    # b) characters as links and text, or text only ?
    # in the linked case we would need to give access to characters
    # and / or creators, so likely just show_characters, etc. to
    # give the text.
    # c) same goes for reprint links
    # d) essentially use for stories the code from exporting as csv ?
    story_set = serializers.StringRelatedField(many=True)


class SeriesSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Series
        exclude = ['created', ]

    country = serializers.PrimaryKeyRelatedField(read_only=True)
    language = serializers.PrimaryKeyRelatedField(read_only=True)
    publication_type = serializers.PrimaryKeyRelatedField(read_only=True)

    # TODO
    # a) filter for deleted issue
    # b) consider *_related
    # c)

    # give links
    issue_set = serializers.HyperlinkedRelatedField(many=True,
                                                    read_only=True,
                                                    view_name='issue-detail')
    # or embed issue serialization (which could embed story)
    # issue_set = IssueSerializer(many=True, read_only=True)


class PublisherSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Publisher
        exclude = ['created', ]

    country = serializers.PrimaryKeyRelatedField(read_only=True)


class BrandSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Brand
        exclude = ['created', ]


class BrandGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BrandGroup
        exclude = ['created', ]


class IndiciaPublisherSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = IndiciaPublisher
        exclude = ['created', ]

    country = serializers.PrimaryKeyRelatedField(read_only=True)
