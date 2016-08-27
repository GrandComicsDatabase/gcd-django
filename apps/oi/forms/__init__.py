# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from apps.oi.models import OngoingReservation
from apps.gcd.models import Series

# Some imports need a 'noqa' because we are only importing them to re-export
# through the forms module as a whole, which flake8 does not understand.
# The 'noqa' goes on the first line of the import, no matter where the
# apparently-unused import is in a multi-line import statement.
from .publisher import (get_publisher_revision_form,
                        get_indicia_publisher_revision_form,
                        get_brand_group_revision_form,
                        get_brand_revision_form,
                        get_brand_use_revision_form)
from .series import get_series_revision_form, get_series_bond_revision_form
from .issue import (    # noqa
    get_issue_revision_form, get_bulk_issue_revision_form)
from .story import get_story_revision_form, get_reprint_revision_form
from .image import get_cover_revision_form
from .image import (    # noqa
    UploadScanForm, UploadVariantScanForm, GatefoldScanForm, UploadImageForm)


def get_revision_form(revision=None, model_name=None, **kwargs):
    if revision is not None and model_name is None:
        model_name = revision.source_name

    if model_name == 'publisher':
        source = None
        if revision is not None:
            source = revision.source
        return get_publisher_revision_form(source=source, **kwargs)

    if model_name == 'indicia_publisher':
        source = None
        if revision is not None:
            source = revision.source
        return get_indicia_publisher_revision_form(source=source, **kwargs)

    if model_name == 'brand_group':
        return get_brand_group_revision_form(**kwargs)

    if model_name == 'brand':
        return get_brand_revision_form(revision=revision, **kwargs)

    if model_name == 'brand_use':
        return get_brand_use_revision_form(**kwargs)

    if model_name == 'series':
        if revision is None:
            return get_series_revision_form(**kwargs)
        if 'publisher' not in kwargs:
            kwargs['publisher'] = revision.publisher
        return get_series_revision_form(source=revision.source, **kwargs)

    if model_name == 'series_bond':
        return get_series_bond_revision_form(**kwargs)

    if model_name == 'issue':
        if revision is not None and 'publisher' not in kwargs:
            kwargs['publisher'] = revision.series.publisher
        return get_issue_revision_form(revision=revision, **kwargs)

    if model_name == 'story':
        return get_story_revision_form(revision, **kwargs)

    if model_name == 'reprint':
        return get_reprint_revision_form(revision, **kwargs)

    if model_name in ['cover', 'image']:
        return get_cover_revision_form(revision, **kwargs)

    raise NotImplementedError


class ForeignKeyField(forms.IntegerField):
    def __init__(self, queryset, target_name=None, **kwargs):
        forms.IntegerField.__init__(self, **kwargs)
        self.queryset = queryset
        if target_name is not None:
            self.target_name = target_name

    def clean(self, value):
        id = forms.IntegerField.clean(self, value)
        if id is None:
            return id
        try:
            return self.queryset.get(id=id)
        except ObjectDoesNotExist:
            raise forms.ValidationError(
                "%d is not the ID of a valid %s" % (id, self.target_name))
        except MultipleObjectsReturned:
            raise forms.ValidationError(
                "%d matched multiple instances of %s" % (id, self.target_name))


class OngoingReservationForm(forms.ModelForm):
    class Meta:
        model = OngoingReservation
        fields = ('series',)
    series = ForeignKeyField(
        queryset=Series.objects.filter(ongoing_reservation__isnull=True,
                                       is_current=True),
        target_name='Available Series',
        help_text='The numeric database ID of a '
                  'series that does not already '
                  'have an ongoing reservation')
