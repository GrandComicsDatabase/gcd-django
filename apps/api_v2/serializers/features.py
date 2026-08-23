# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Serializers for v2 Feature endpoints."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.gcd.models import Feature, FeatureLogo, FeatureNameDetail


def _feature_type_reference(feature_type):
    """Return a minimal Feature Type reference."""
    return {
        'id': feature_type.pk,
        'name': feature_type.name,
    }


def _related_feature_reference(feature):
    """Return a related Feature reference for normalized relations."""
    return {
        'id': feature.pk,
        'name': feature.name,
        'disambiguation': feature.disambiguation,
        'feature_type': _feature_type_reference(feature.feature_type),
    }


class FeatureLogoSerializer(serializers.ModelSerializer):
    """Serialize an active Feature Logo reference."""

    class Meta:
        """Serializer metadata for Feature Logo fields."""

        model = FeatureLogo
        fields = (
            'id',
            'name',
            'generic',
            'year_began',
            'year_ended',
            'year_began_uncertain',
            'year_ended_uncertain',
        )


class FeatureNameDetailSerializer(serializers.ModelSerializer):
    """Serialize active names for a Feature."""

    class Meta:
        """Serializer metadata for Feature name-detail fields."""

        model = FeatureNameDetail
        fields = (
            'id',
            'name',
            'sort_name',
            'is_official_name',
        )


class FeatureTypeReferenceSerializer(serializers.Serializer):
    """Describe a Feature Type nested reference."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class RelatedFeatureReferenceSerializer(serializers.Serializer):
    """Describe the other Feature in a normalized relation."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    disambiguation = serializers.CharField()
    feature_type = FeatureTypeReferenceSerializer()


class FeatureRelationTypeReferenceSerializer(serializers.Serializer):
    """Describe a directional Feature Relation Type."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()


class NormalizedFeatureRelationSerializer(serializers.Serializer):
    """Serialize a Feature Relation relative to the requested Feature."""

    id = serializers.IntegerField()
    direction = serializers.ChoiceField(choices=('outgoing', 'incoming'))
    relation_type = FeatureRelationTypeReferenceSerializer()
    feature = RelatedFeatureReferenceSerializer()
    notes = serializers.CharField()


class FeatureListSerializer(serializers.ModelSerializer):
    """Serialize trimmed Feature list rows."""

    feature_type = serializers.SerializerMethodField()
    language = serializers.SlugRelatedField(
        read_only=True,
        slug_field='code',
    )

    class Meta:
        """Serializer metadata for Feature list fields."""

        model = Feature
        fields = (
            'id',
            'name',
            'sort_name',
            'disambiguation',
            'feature_type',
            'language',
            'genre',
            'year_first_published',
            'created',
            'modified',
        )

    def get_feature_type(self, obj):
        """Return the nested Feature Type reference."""
        return _feature_type_reference(obj.feature_type)


class FeatureSerializer(FeatureListSerializer):
    """Serialize complete Feature detail rows."""

    keywords = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )
    name_details = serializers.SerializerMethodField()
    logos = serializers.SerializerMethodField()
    relations = serializers.SerializerMethodField()

    class Meta(FeatureListSerializer.Meta):
        """Serializer metadata for Feature detail fields."""

        fields = FeatureListSerializer.Meta.fields + (
            'year_first_published_uncertain',
            'description',
            'notes',
            'name_details',
            'keywords',
            'logos',
            'relations',
        )

    @extend_schema_field(FeatureNameDetailSerializer(many=True))
    def get_name_details(self, obj):
        """Return ordered active names for the Feature."""
        name_details = getattr(obj, 'active_name_detail_list', None)
        if name_details is None:
            name_details = obj.feature_names.filter(deleted=False).order_by(
                'sort_name',
                'id',
            )
        return FeatureNameDetailSerializer(name_details, many=True).data

    def get_logos(self, obj):
        """Return ordered active Feature Logos."""
        name_details = getattr(obj, 'active_name_detail_list', None)
        if name_details is None:
            logos = (
                FeatureLogo.objects.filter(
                    deleted=False,
                    feature_name__deleted=False,
                    feature_name__feature=obj,
                )
                .distinct()
                .order_by('sort_name', 'id')
            )
        else:
            logos_by_id = {
                logo.pk: logo
                for name_detail in name_details
                for logo in name_detail.active_feature_logo_list
            }
            logos = sorted(
                logos_by_id.values(),
                key=lambda logo: (logo.sort_name, logo.pk),
            )
        return FeatureLogoSerializer(logos, many=True).data

    def get_relations(self, obj):
        """Return one normalized collection for both relation directions."""
        outgoing = getattr(obj, 'outgoing_feature_relation_list', None)
        if outgoing is None:
            outgoing = (
                obj.to_related_feature.filter(
                    from_feature__deleted=False,
                    to_feature__deleted=False,
                )
                .select_related('relation_type', 'to_feature__feature_type')
                .order_by(
                    'relation_type__name',
                    'to_feature__sort_name',
                    'id',
                )
            )
        incoming = getattr(obj, 'incoming_feature_relation_list', None)
        if incoming is None:
            incoming = (
                obj.from_related_feature.filter(
                    from_feature__deleted=False,
                    to_feature__deleted=False,
                )
                .select_related(
                    'relation_type',
                    'from_feature__feature_type',
                )
                .order_by(
                    'relation_type__name',
                    'from_feature__sort_name',
                    'id',
                )
            )

        relations = [
            {
                'id': relation.pk,
                'direction': 'outgoing',
                'relation_type': {
                    'id': relation.relation_type_id,
                    'name': relation.relation_type.name,
                    'description': relation.relation_type.description,
                },
                'feature': _related_feature_reference(relation.to_feature),
                'notes': relation.notes,
            }
            for relation in outgoing
        ]
        relations.extend(
            {
                'id': relation.pk,
                'direction': 'incoming',
                'relation_type': {
                    'id': relation.relation_type_id,
                    'name': relation.relation_type.name,
                    'description': (
                        relation.relation_type.reverse_description
                    ),
                },
                'feature': _related_feature_reference(
                    relation.from_feature,
                ),
                'notes': relation.notes,
            }
            for relation in incoming
        )
        return NormalizedFeatureRelationSerializer(
            relations,
            many=True,
        ).data
