# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 issue endpoints."""

from rest_framework import serializers

from apps.api_v2.utils.credits import collect_credit_strings
from apps.gcd.models import Issue, Story


def _cover_url(issue):
    """Return the best available cover URL for an issue."""
    covers = getattr(issue, 'active_cover_list', None)
    if covers is None:
        covers = list(issue.cover_set.filter(deleted=False).order_by('id'))
    if not covers and issue.variant_of_id and issue.variant_cover_status == 1:
        base_issue = getattr(issue, 'variant_of', None)
        base_covers = getattr(base_issue, 'active_cover_list', None)
        if base_covers is None and base_issue is not None:
            base_covers = list(
                base_issue.cover_set.filter(deleted=False).order_by('id')
            )
        covers = base_covers or []
    if not covers:
        return ''
    cover = covers[0]
    return f'{cover.get_base_url()}/w400/{cover.id}.jpg'


class StorySerializer(serializers.ModelSerializer):
    """Serialize nested stories on issue detail responses."""

    type = serializers.SerializerMethodField()
    script = serializers.SerializerMethodField()
    pencils = serializers.SerializerMethodField()
    inks = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()
    letters = serializers.SerializerMethodField()
    editing = serializers.SerializerMethodField()
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta:
        """Serializer metadata for issue detail story selection."""

        model = Story
        fields = (
            'id',
            'type',
            'title',
            'feature',
            'sequence_number',
            'page_count',
            'script',
            'pencils',
            'inks',
            'colors',
            'letters',
            'editing',
            'job_number',
            'genre',
            'first_line',
            'characters',
            'synopsis',
            'notes',
            'keywords',
        )

    def get_type(self, obj):
        """Return the minimal nested story type reference."""
        return {
            'id': obj.type_id,
            'name': obj.type.name,
        }

    def get_script(self, obj):
        """Return story script credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'script',
            prefetched_attr='active_credit_list',
        )

    def get_pencils(self, obj):
        """Return story pencil credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'pencils',
            prefetched_attr='active_credit_list',
        )

    def get_inks(self, obj):
        """Return story ink credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'inks',
            prefetched_attr='active_credit_list',
        )

    def get_colors(self, obj):
        """Return story color credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'colors',
            prefetched_attr='active_credit_list',
        )

    def get_letters(self, obj):
        """Return story lettering credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'letters',
            prefetched_attr='active_credit_list',
        )

    def get_editing(self, obj):
        """Return story editing credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'editing',
            prefetched_attr='active_credit_list',
        )


class IssueListSerializer(serializers.ModelSerializer):
    """Serialize issue list responses for the v2 public API."""

    series = serializers.SerializerMethodField()
    descriptor = serializers.SerializerMethodField()
    editing_credits = serializers.SerializerMethodField()
    indicia_publisher = serializers.SerializerMethodField()
    brand_emblems = serializers.SerializerMethodField()
    variant_of = serializers.IntegerField(
        source='variant_of_id', read_only=True
    )
    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )
    cover_url = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata for issue list field selection."""

        model = Issue
        fields = (
            'id',
            'series',
            'number',
            'volume',
            'descriptor',
            'variant_name',
            'title',
            'publication_date',
            'key_date',
            'on_sale_date',
            'price',
            'page_count',
            'editing_credits',
            'indicia_publisher',
            'brand_emblems',
            'isbn',
            'barcode',
            'rating',
            'indicia_frequency',
            'notes',
            'variant_of',
            'keywords',
            'created',
            'modified',
            'cover_url',
        )

    def get_series(self, obj):
        """Return the minimal nested series reference."""
        return {
            'id': obj.series_id,
            'name': obj.series.name,
        }

    def get_descriptor(self, obj):
        """Return the full issue descriptor."""
        return obj.full_descriptor

    def get_editing_credits(self, obj):
        """Return issue editing credits as plain-text entries."""
        return collect_credit_strings(
            obj,
            'editing',
            prefetched_attr='active_credit_list',
        )

    def get_indicia_publisher(self, obj):
        """Return the minimal nested indicia publisher reference."""
        if obj.indicia_publisher_id is None:
            return None
        return {
            'id': obj.indicia_publisher_id,
            'name': obj.indicia_publisher.name,
        }

    def get_brand_emblems(self, obj):
        """Return nested brand emblem references sorted by name."""
        return [
            {'id': brand.id, 'name': brand.name}
            for brand in sorted(
                obj.brand_emblem.all(),
                key=lambda brand: (brand.name, brand.id),
            )
        ]

    def get_cover_url(self, obj):
        """Return the first available cover URL."""
        return _cover_url(obj)


class IssueDetailSerializer(IssueListSerializer):
    """Serialize issue detail responses with nested stories."""

    stories = serializers.SerializerMethodField()

    class Meta(IssueListSerializer.Meta):
        """Serializer metadata for issue detail field selection."""

        fields = IssueListSerializer.Meta.fields + ('stories',)

    def get_stories(self, obj):
        """Return nested active stories for the issue detail response."""
        stories = getattr(obj, 'active_story_list', None)
        if stories is None:
            stories = obj.active_stories().order_by('sequence_number', 'id')
        return StorySerializer(stories, many=True).data
