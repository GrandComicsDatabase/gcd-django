# -*- coding: utf-8 -*-


from collections import OrderedDict

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from .support import (
    _get_comments_form_field, _set_help_labels, _clean_keywords,
    GENERIC_ERROR_MESSAGE, PUBLISHER_HELP_LINKS, PUBLISHER_HELP_TEXTS,
    INDICIA_PUBLISHER_HELP_LINKS, BRAND_HELP_LINKS)

from apps.oi.models import (
    PublisherRevision, IndiciaPublisherRevision, BrandGroupRevision,
    BrandRevision, BrandUseRevision, get_brand_use_field_list)

from apps.stddata.models import Country
from apps.gcd.models import BrandGroup


def get_publisher_revision_form(source=None, user=None):
    class RuntimePublisherRevisionForm(PublisherRevisionForm):
        if source is not None:
            # Don't allow country to be un-set:
            if source.country.code == 'xx':
                country_queryset = Country.objects.all()
            else:
                country_queryset = Country.objects.exclude(code='xx')
            country = forms.ModelChoiceField(queryset=country_queryset,
                                             empty_label=None)

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, PUBLISHER_HELP_LINKS)
            return super(RuntimePublisherRevisionForm, self).as_table()
    return RuntimePublisherRevisionForm


def _get_publisher_fields(middle=None):
    first = ['name', 'year_began', 'year_began_uncertain',
                     'year_ended', 'year_ended_uncertain']
    last = ['url', 'notes', 'keywords']
    if middle is not None:
        first.extend(middle)
    first.extend(last)
    return first


class PublisherRevisionForm(forms.ModelForm):
    class Meta:
        model = PublisherRevision
        fields = _get_publisher_fields(middle=('country',))
        widgets = {'name': forms.TextInput(attrs={'autofocus': ''})}
        help_texts = PUBLISHER_HELP_TEXTS

    country = forms.ModelChoiceField(
        queryset=Country.objects.exclude(code='xx'))
    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd


def get_indicia_publisher_revision_form(source=None, user=None):
    class RuntimeIndiciaPublisherRevisionForm(IndiciaPublisherRevisionForm):
        if source is not None:
            # Don't allow country to be un-set:
            country = forms.ModelChoiceField(
                empty_label=None,
                queryset=Country.objects.exclude(code='xx'))

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, INDICIA_PUBLISHER_HELP_LINKS)
            return super(RuntimeIndiciaPublisherRevisionForm, self).as_table()

    return RuntimeIndiciaPublisherRevisionForm


class IndiciaPublisherRevisionForm(PublisherRevisionForm):
    class Meta(PublisherRevisionForm.Meta):
        model = IndiciaPublisherRevision
        fields = _get_publisher_fields(middle=('is_surrogate', 'country'))

    name = forms.CharField(
        widget=forms.TextInput(attrs={'autofocus': ''}),
        max_length=255,
        required=True,
        help_text='The name exactly as it appears in the indicia or colophon, '
                  'including punctuation, abbreviations, suffixes like ", '
                  'Inc.", etc. Do not move articles to the end of the name.')

    is_surrogate = forms.BooleanField(
        required=False,
        label='Surrogate',
        help_text='Check if this was an independent company serving as a '
                  'surrogate for the master publisher, rather than a company '
                  'belonging to the master publisher.')

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd


def get_brand_group_revision_form(source=None, user=None):
    class RuntimeBrandGroupRevisionForm(BrandGroupRevisionForm):
        if source is None:
            name = forms.CharField(
                widget=forms.TextInput(attrs={'autofocus': ''}),
                max_length=255,
                help_text='The name of the new brand group.')

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BRAND_HELP_LINKS)
            return super(RuntimeBrandGroupRevisionForm, self).as_table()
    return RuntimeBrandGroupRevisionForm


class BrandGroupRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandGroupRevision
        fields = _get_publisher_fields()

    name = forms.CharField(
        widget=forms.TextInput(attrs={'autofocus': ''}),
        max_length=255,
        help_text='The name of the brand group.')

    year_began = forms.IntegerField(
        required=False,
        help_text='The first year the brand group was used.')
    year_began_uncertain = forms.BooleanField(
        required=False,
        help_text='Check if you are not certain of the first year the brand '
                  'group was used.')

    year_ended = forms.IntegerField(
        required=False,
        help_text='The last year the brand group was used.  Leave blank if '
                  'currently in use.')
    year_ended_uncertain = forms.BooleanField(
        required=False,
        help_text='Check if you are not certain of the last year the brand '
                  'group was used, or if you are not certain whether it is '
                  'still in use.')

    url = forms.URLField(
        required=False,
        help_text='The official web site of the brand.  Leave blank if the '
                  'publisher does not have a specific web site for the brand '
                  'group.')

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd


def get_brand_revision_form(user=None, revision=None,
                            brand_group=None, publisher=None):
    initial = []

    # either revision, brand_group or publisher is set, but never two
    if revision:
        if revision.source:
            pubs = revision.source.in_use.all().values_list('publisher_id',
                                                            flat=True)
            queryset = BrandGroup.objects.filter(parent__in=pubs,
                                                 deleted=False)
        else:
            queryset = BrandGroup.objects.none()
        if revision.group.count():
            queryset = (queryset | revision.group.all()).distinct()
    elif brand_group:
        initial = [brand_group.id]
        queryset = BrandGroup.objects.filter(id=brand_group.id)
    elif publisher:
        queryset = BrandGroup.objects.filter(parent=publisher.id,
                                             deleted=False)
    else:
        raise NotImplementedError

    class RuntimeBrandRevisionForm(BrandRevisionForm):
        def __init__(self, *args, **kw):
            super(BrandRevisionForm, self).__init__(*args, **kw)
            # brand_group_other_publisher_id is last field, move it after group
            ordering = list(self.fields.keys())
            ordering.insert(ordering.index('group') + 1,
                            ordering.pop())
            new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
            self.fields = new_fields
        group = forms.ModelMultipleChoiceField(
            required=True,
            widget=FilteredSelectMultiple('Brand Groups', False),
            queryset=queryset,
            initial=initial)
        # TODO currently a second group can only added for existing brands
        if revision and revision.source:
            brand_group_other_publisher_id = forms.IntegerField(
                required=False,
                label="Add Brand Group",
                help_text="One can add a brand group from a different publisher "
                          "by id. If an id is entered the submit will return for "
                          "confirmation.")

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BRAND_HELP_LINKS)
            return super(RuntimeBrandRevisionForm, self).as_table()
    return RuntimeBrandRevisionForm


class BrandRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandRevision
        fields = _get_publisher_fields(middle=('group',))

    name = forms.CharField(
        widget=forms.TextInput(attrs={'autofocus': ''}),
        max_length=255,
        help_text='The name of the brand emblem as it appears on the logo.  '
                  'If the logo does not use words, then the name of the '
                  'brand as it is commonly used.  Consult an editor if in '
                  'doubt.')

    year_began = forms.IntegerField(
        required=False,
        help_text='The first year the brand emblem was used.')

    year_began_uncertain = forms.BooleanField(
        required=False,
        help_text='Check if you are not certain of the first year the brand '
                  'emblem was used.')

    year_ended = forms.IntegerField(
        required=False,
        help_text='The last year the brand emblem was used.  Leave blank if '
                  'currently in use.')
    year_ended_uncertain = forms.BooleanField(
        required=False,
        help_text='Check if you are not certain of the last year the '
                  'brand emblem was used, or if you are not certain whether '
                  'it is still in use.')

    url = forms.URLField(
        required=False,
        help_text='The official web site of the brand.  Leave blank if the '
                  'publisher does not have a specific web site for the brand.')

    comments = _get_comments_form_field()

    def clean_keywords(self):
        return _clean_keywords(self.cleaned_data)

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        if 'name' in cd:
            cd['name'] = cd['name'].strip()
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        # this checks if we are adding a new brand or not
        if 'brand_group_other_publisher_id' in cd:
            if cd['brand_group_other_publisher_id']:
                brand_group = BrandGroup.objects.filter(
                    id=cd['brand_group_other_publisher_id'], deleted=False)
                if brand_group:
                    brand_group = brand_group[0]
                    # need to add directly to revision, otherwise validation
                    # fails
                    self.instance.group.add(brand_group)
                    # self.data is immutable, need copy
                    data = self.data.copy()
                    data['brand_group_other_publisher_id'] = None
                    self.data = data
                    raise forms.ValidationError(
                        "Please confirm selection of brand group '%s'." %
                        brand_group)
                else:
                    raise forms.ValidationError(
                        "A brand group with id %d does not exist." %
                        cd['brand_group_other_publisher_id'])
        return cd


def get_brand_use_revision_form(user=None):
    class RuntimeBrandUseRevisionForm(BrandUseRevisionForm):
        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, BRAND_HELP_LINKS)
            return super(RuntimeBrandUseRevisionForm, self).as_table()
    return RuntimeBrandUseRevisionForm


class BrandUseRevisionForm(forms.ModelForm):
    class Meta:
        model = BrandUseRevision
        fields = get_brand_use_field_list()

    year_began = forms.IntegerField(
        required=False,
        help_text='The first year the brand was at the publisher.')
    year_began_uncertain = forms.BooleanField(
        required=False,
        help_text='Check if you are not certain of the first year the '
                  'brand was used.')

    year_ended = forms.IntegerField(
        required=False,
        help_text='The last year the brand was used at the publisher. '
                  ' Leave blank if currently in use.')
    year_ended_uncertain = forms.BooleanField(
        required=False,
        help_text='Check if you are not certain of the last year the brand '
                  'was used, or if you are not certain whether it is still '
                  'in use.')

    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)
        cd['notes'] = cd['notes'].strip()
        cd['comments'] = cd['comments'].strip()
        return cd
