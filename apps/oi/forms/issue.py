# -*- coding: utf-8 -*-


import re
from collections import OrderedDict
from math import log10

from django import forms
from django.db.models import Q
from django.forms.widgets import HiddenInput
from django.forms.models import inlineformset_factory

from dal import autocomplete

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML

from .custom_layout_object import Formset, BaseField
from .support import (GENERIC_ERROR_MESSAGE, ISSUE_HELP_LINKS,
                      VARIANT_NAME_HELP_TEXT, VARIANT_COVER_STATUS_HELP_TEXT,
                      ISSUE_LABELS, ISSUE_HELP_TEXTS,
                      _set_help_labels, _init_no_isbn, _init_no_barcode,
                      _get_comments_form_field, _clean_keywords,
                      HiddenInputWithHelp, PageCountInput, BrandEmblemSelect)

from apps.oi.models import CTYPES, IssueRevision, IssueCreditRevision,\
                           PublisherCodeNumberRevision, get_issue_field_list
from apps.gcd.models import Issue, Brand, IndiciaPublisher, CreditType,\
                            CreatorNameDetail, IndiciaPrinter


def get_issue_revision_form(publisher, series=None, revision=None,
                            variant_of=None, user=None, edit_with_base=False):
    if series is None and revision is not None:
        series = revision.series
    if revision is not None and revision.variant_of:
        variant_of = revision.variant_of

    class RuntimeIssueRevisionForm(IssueRevisionForm):
        class Meta(IssueRevisionForm.Meta):
            pass

        def __init__(self, *args, **kwargs):
            super(RuntimeIssueRevisionForm, self).__init__(*args, **kwargs)
            self.fields['brand'].queryset = \
                series.publisher.active_brand_emblems_no_pending()
            self.fields['indicia_publisher'].queryset = \
                series.publisher.active_indicia_publishers_no_pending()
            position = self.helper['editing'].slice[0][0][0]
            self.helper.layout[position].append(
              HTML('<th></th><td><input type="submit" name="save_migrate"'
                   ' value="save and migrate editing"  /></td>'))

            issue_year = None
            if revision and revision.key_date:
                issue_year = int(revision.key_date[:4])
            elif revision and revision.year_on_sale and \
                    int(log10(revision.year_on_sale)) + 1 == 4:
                issue_year = revision.year_on_sale
            if issue_year:
                started_before = Q(in_use__year_began__lte=issue_year,
                                   in_use__publisher=series.publisher)
                no_start = Q(in_use__year_began=None,
                             in_use__publisher=series.publisher)
                not_ended_before = (Q(in_use__year_ended__gte=issue_year,
                                      in_use__publisher=series.publisher) |
                                    Q(in_use__year_ended=None,
                                      in_use__publisher=series.publisher))

                brands = self.fields['brand'].queryset \
                             .filter(in_use__publisher=series.publisher) \
                             .filter((started_before & not_ended_before) |
                                     (no_start & not_ended_before))

                self.fields['brand'].queryset = brands.distinct()
                self.fields['indicia_publisher'].queryset = \
                    self.fields['indicia_publisher'].queryset\
                    .exclude(year_ended__lt=issue_year)
                self.fields['indicia_publisher'].queryset = \
                    self.fields['indicia_publisher'].queryset\
                    .exclude(year_began__gt=issue_year)
            else:
                if series.year_began:
                    self.fields['brand'].queryset = \
                        self.fields['brand'].queryset \
                            .exclude(year_ended__lt=series.year_began)
                    self.fields['indicia_publisher'].queryset = \
                        self.fields['indicia_publisher'].queryset \
                            .exclude(year_ended__lt=series.year_began)
                if series.year_ended:
                    self.fields['brand'].queryset = \
                        self.fields['brand'].queryset \
                            .exclude(year_began__gt=series.year_ended)
                    self.fields['indicia_publisher'].queryset = \
                        self.fields['indicia_publisher'].queryset \
                            .exclude(year_began__gt=series.year_ended)
            if revision:
                if revision.brand and \
                        revision.brand not in self.fields['brand'].queryset:
                    self.fields['brand'].queryset = (
                        self.fields['brand'].queryset |
                        Brand.objects.filter(id=revision.brand.id).distinct())
                if revision.indicia_publisher and \
                        revision.indicia_publisher not in \
                        self.fields['indicia_publisher'].queryset:
                    self.fields['indicia_publisher'].queryset = (
                        self.fields['indicia_publisher'].queryset |
                        IndiciaPublisher.objects.filter(
                            id=revision.indicia_publisher.id))

            self.fields['no_isbn'].initial = _init_no_isbn(series, None)
            self.fields['no_barcode'].initial = _init_no_barcode(series, None)

        turned_off_list = ''

        if not series.has_issue_title:
            no_title = forms.BooleanField(widget=forms.HiddenInput,
                                          required=False)
            title = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'title, '

        if not series.has_volume:
            no_volume = forms.BooleanField(widget=forms.HiddenInput,
                                           required=False)
            display_volume_with_number = forms.BooleanField(
                widget=forms.HiddenInput, required=False)
            volume = forms.CharField(widget=HiddenInput, required=False)
            volume_not_printed = forms.BooleanField(widget=forms.HiddenInput,
                                                    required=False)
            turned_off_list += 'volume, '

        if not series.has_indicia_frequency:
            no_indicia_frequency = forms.BooleanField(widget=forms.HiddenInput,
                                                      required=False)
            indicia_frequency = forms.CharField(widget=HiddenInput,
                                                required=False)
            turned_off_list += 'indicia_frequency, '

        if not series.has_indicia_printer:
            no_indicia_printer = forms.BooleanField(widget=forms.HiddenInput,
                                                    required=False)
            indicia_printer = forms.ModelMultipleChoiceField(
              widget=forms.MultipleHiddenInput,
              queryset=IndiciaPrinter.objects.all(),
              required=False)
            turned_off_list += 'indicia_printer, '

        if not series.has_isbn:
            no_isbn = forms.BooleanField(widget=forms.HiddenInput,
                                         required=False)
            isbn = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'isbn, '

        if not series.has_barcode:
            no_barcode = forms.BooleanField(widget=forms.HiddenInput,
                                            required=False)
            barcode = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'barcode, '

        if not series.has_rating:
            no_rating = forms.BooleanField(widget=forms.HiddenInput,
                                           required=False)
            rating = forms.CharField(widget=HiddenInput, required=False)
            turned_off_list += 'publisher age guidelines'

        if turned_off_list:
            turned_off_help = forms.CharField(
                widget=HiddenInputWithHelp,
                required=False,
                label='Deactivated fields',
                help_text='The fields <i>%s</i> are deactivated for this '
                          'series. To enter a value for one of these the '
                          'corresponding series setting has to be changed.' %
                          turned_off_list)

        def clean_year_on_sale(self):
            year_on_sale = self.cleaned_data['year_on_sale']
            year_string = str(year_on_sale)[:2]
            if year_on_sale is not None and (year_string < '18' or
                                             year_string > '20' or
                                             len(str(year_on_sale)) > 4):
                raise forms.ValidationError('Unreasonable year entered.')
            return year_on_sale

        def clean_month_on_sale(self):
            month_on_sale = self.cleaned_data['month_on_sale']

            if month_on_sale is not None and \
               month_on_sale not in list(range(1, 13)):
                raise forms.ValidationError(
                    'If entered, month needs to be between 1 and 12.')
            return month_on_sale

        def clean_day_on_sale(self):
            day_on_sale = self.cleaned_data['day_on_sale']

            if day_on_sale is not None and \
               day_on_sale not in list(range(1, 32)):
                raise forms.ValidationError(
                    'If entered, day needs to be between 1 and 31.')
            return day_on_sale

        def clean_key_date(self):
            key_date = self.cleaned_data['key_date']
            if key_date is not None:
                key_date = key_date.replace('.', '-')
            return key_date

        def clean_keywords(self):
            return _clean_keywords(self.cleaned_data)

        def clean(self):
            cd = self.cleaned_data

            if self._errors:
                raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

            cd['number'] = cd['number'].strip()
            cd['volume'] = cd['volume'].strip()
            cd['publication_date'] = cd['publication_date'].strip()
            cd['key_date'] = cd['key_date'].strip()
            cd['indicia_frequency'] = cd['indicia_frequency'].strip()
            cd['price'] = cd['price'].strip()
            cd['editing'] = cd['editing'].strip()
            cd['notes'] = cd['notes'].strip()
            cd['comments'] = cd['comments'].strip()
            cd['isbn'] = cd['isbn'].strip()
            if 'variant_name' in cd:
                cd['variant_name'] = cd['variant_name'].strip()

            if 'variant_cover_status' in cd and cd['variant_cover_status'] < 3:
                if revision and revision.changeset.storyrevisions.filter(
                  issue=revision.issue, deleted=False).exists():
                    raise forms.ValidationError(
                        'A cover sequence exists for this variant. Before '
                        'changing the variant cover status please first mark '
                        'it for delete or remove it.')


            if cd['volume'] != "" and cd['no_volume']:
                raise forms.ValidationError(
                    'You cannot specify a volume and check "no volume" at '
                    'the same time')

            if cd['no_title'] and cd['title']:
                raise forms.ValidationError(
                    'You cannot specify a title and check "no title" at the '
                    'same time.')

            if cd['no_editing']:
                nr_credit_forms = self.data['issue_credit_revisions-TOTAL_FORMS']
                seq_type_found = False
                for i in range(int(nr_credit_forms)):
                    delete_i = 'issue_credit_revisions-%d-DELETE' % i
                    form_deleted = False
                    if delete_i in self.data:
                        if self.data[delete_i]:
                            form_deleted = True
                    if not form_deleted:
                        credit_type = \
                            self.data['issue_credit_revisions-%d-credit_type'
                                      % i]
                        if credit_type == '6':
                            seq_type_found = True
                        elif credit_type:
                            raise forms.ValidationError(
                              ['Unsupported credit type.'])

                # no_editing is present, no need to check here again
                if cd['editing'] != "" or seq_type_found:
                    raise forms.ValidationError(
                        ['%s field and No %s checkbox cannot both be filled'
                         ' in.' % ("Editing", "Editing")])

            if cd['no_brand'] and cd['brand'] is not None:
                raise forms.ValidationError(
                    'You cannot specify a brand and check "no brand" at the '
                    'same time.')

            if cd['no_indicia_frequency'] and cd['indicia_frequency']:
                raise forms.ValidationError(
                    'You cannot specify an indicia frequency and check '
                    '"no indicia frequency" at the same time.')

            if cd['no_indicia_printer'] and cd['indicia_printer']:
                raise forms.ValidationError(
                    'You cannot specify an indicia printer and check '
                    '"no indicia printer" at the same time.')

            if cd['no_isbn'] and cd['isbn']:
                raise forms.ValidationError(
                    'You cannot specify an isbn and check "no isbn" at the '
                    'same time.')

            if cd['on_sale_date'] and (cd['year_on_sale'] or
                                       cd['month_on_sale'] or
                                       cd['day_on_sale']):
                raise forms.ValidationError(
                    'You can only use either the on-sale date-field or the '
                    'three separate date fields, not both data entering '
                    'options.')
            elif cd['on_sale_date']:
                # only full dates can be entered this way
                if cd['on_sale_date'].year < 1800 or \
                   cd['on_sale_date'].year >= 2100:
                    raise forms.ValidationError('Unreasonable year entered.')
                cd['year_on_sale'] = cd['on_sale_date'].year
                cd['month_on_sale'] = cd['on_sale_date'].month
                cd['day_on_sale'] = cd['on_sale_date'].day

            if cd['key_date'] == '' and (cd['year_on_sale'] or
                                         cd['publication_date']):
                raise forms.ValidationError(
                  'Dates are present, but the key date is empty.')

            if cd['page_count_uncertain'] and not cd['page_count']:
                raise forms.ValidationError(
                    'You cannot check page count '
                    'uncertain without a page count.')

            if cd['no_barcode'] and cd['barcode']:
                raise forms.ValidationError(
                    'You cannot specify a barcode and check "no barcode" at '
                    'the same time.')

            if cd['barcode']:
                cd['barcode'] = cd['barcode'].replace('-', '').replace(' ', '')
                cd['barcode'] = cd['barcode'].replace(';', '; ')

            if cd['no_rating'] and cd['rating']:
                raise forms.ValidationError(
                    "You cannot specify a publisher's age guideline and check "
                    " no publisher's age guideline at the same time.")

            return cd

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, ISSUE_HELP_LINKS)
            return super(RuntimeIssueRevisionForm, self).as_table()

    if variant_of:
        class RuntimeAddVariantIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta(RuntimeIssueRevisionForm.Meta):
                fields = RuntimeIssueRevisionForm.Meta.fields
                fields = fields[0:1] + ['variant_name'] \
                                     + ['variant_cover_status'] + fields[1:]

                widgets = RuntimeIssueRevisionForm.Meta.widgets
                widgets['variant_name'] = \
                    forms.TextInput(attrs={'class': 'wide'})
                help_texts = RuntimeIssueRevisionForm.Meta.help_texts
                help_texts['variant_name'] = VARIANT_NAME_HELP_TEXT
                help_texts['variant_cover_status'] = \
                    VARIANT_COVER_STATUS_HELP_TEXT

                labels = RuntimeIssueRevisionForm.Meta.labels

                if revision is None or revision.source is None:
                    fields = ['after'] + fields
                    labels['after'] = 'Add this issue after'

                    if not edit_with_base:
                        fields = ['reservation_requested'] + fields

                        help_texts = RuntimeIssueRevisionForm.Meta.help_texts
                        help_texts.update(
                          reservation_requested='Check this box to have this '
                                                'issue reserved to you '
                                                'automatically when it is '
                                                'approved, unless someone '
                                                "has acquired the series' "
                                                'ongoing reservation before '
                                                'then.')

            def __init__(self, *args, **kwargs):
                super(RuntimeAddVariantIssueRevisionForm,
                      self).__init__(*args, **kwargs)
                # can add after one of the variants
                if 'after' in self.fields:
                    self.fields['after'].queryset = (
                        variant_of.variant_set.filter(deleted=False) |
                        Issue.objects.filter(id=variant_of.id))
                    self.fields['after'].empty_label = None

        return RuntimeAddVariantIssueRevisionForm

    if revision is None or revision.source is None:
        class RuntimeAddIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta(RuntimeIssueRevisionForm.Meta):
                fields = RuntimeIssueRevisionForm.Meta.fields
                fields = ['after'] + fields
                widgets = RuntimeIssueRevisionForm.Meta.widgets
                labels = RuntimeIssueRevisionForm.Meta.labels
                labels['after'] = 'Add this issue after'

                if series.get_ongoing_reservation() is None:
                    fields = ['reservation_requested'] + fields

                    help_texts = RuntimeIssueRevisionForm.Meta.help_texts
                    help_texts.update(
                        reservation_requested='Check this box to have this '
                                              'issue reserved to you '
                                              'automatically when it is '
                                              'approved, unless someone '
                                              "has acquired the series' "
                                              'ongoing reservation before '
                                              'then.')

            def __init__(self, *args, **kwargs):
                super(RuntimeAddIssueRevisionForm,
                      self).__init__(*args, **kwargs)
                self.fields['after'].queryset = series.active_issues()
                self.fields['after'].empty_label = '[add as first issue]'

        return RuntimeAddIssueRevisionForm

    # the other issuerevision from 'variant_add' was taken care of above
    if (revision.changeset.change_type == CTYPES['variant_add']) or \
            revision.issue.variant_set.count():
        class RuntimeBaseIssueRevisionForm(RuntimeIssueRevisionForm):
            class Meta(RuntimeIssueRevisionForm.Meta):
                fields = RuntimeIssueRevisionForm.Meta.fields
                fields = fields[0:1] + ['variant_name'] + fields[1:]

                widgets = RuntimeIssueRevisionForm.Meta.widgets
                widgets['variant_name'] = \
                    forms.TextInput(attrs={'class': 'wide'})
                help_texts = RuntimeIssueRevisionForm.Meta.help_texts
                help_texts['variant_name'] = VARIANT_NAME_HELP_TEXT
        return RuntimeBaseIssueRevisionForm

    return RuntimeIssueRevisionForm


class IssueCreditRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueCreditRevision
        fields = ['creator', 'credit_type', 'is_credited', 'credited_as',
                  'uncertain', 'is_sourced', 'sourced_by', 'credit_name']
        help_texts = {
            'credit_name':
                'Enter here additional specifications for the credit, for '
                'example <i>associate editor</i>, or <i>design</i>.',
            'is_credited':
                'Check in case the creator is credited. If the credited name '
                'is not the selected creator name, enter the credited name'
                ' in the unfolded credited as field.',
            'credited_as':
                'Enter a name if the credited name is unusual and '
                'therefore not a creator name record.',
            'is_sourced':
                'Check in case the entered credit has external sources.',
            'sourced_by':
                'A concise and clear description of the external source of '
                'the credit.'
        }
        labels = {'credit_name': 'Credit description'}

    def __init__(self, *args, **kwargs):
        super(IssueCreditRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(*(f for f in self.fields))
        self.fields['credit_type'].queryset = CreditType.objects \
            .filter(id=6)
        if self.instance.id:
            self.fields['credit_type'].empty_label = None

    creator = forms.ModelChoiceField(
      queryset=CreatorNameDetail.objects.all(),
      widget=autocomplete.ModelSelect2(url='creator_name_autocomplete',
                                       attrs={'style': 'min-width: 60em'}),
      required=True,
      help_text='By entering (any part of) a name select a creator from the'
                ' database.'
    )

    def clean(self):
        cd = self.cleaned_data
        if cd['credited_as'] and not cd['is_credited']:
            raise forms.ValidationError(
              ['Is credited needs to be selected when entering a name as '
               'credited.'])

        if cd['credited_as'] and 'creator' in cd and \
           cd['credited_as'] == cd['creator'].name:
            raise forms.ValidationError(
              ['Name entered as "credited as" is identicial to creator name.']
            )


IssueRevisionFormSet = inlineformset_factory(
    IssueRevision, IssueCreditRevision, form=IssueCreditRevisionForm,
    can_delete=True, extra=1)


# not sure why we need this, the docs say that extra would be on top
# of the number of forms initialized, but that doesn't work, or is
# meant differently
def get_issue_revision_form_set_extra(extra=1):
    return inlineformset_factory(
        IssueRevision, IssueCreditRevision, form=IssueCreditRevisionForm,
        can_delete=True, extra=extra)


class PublisherCodeNumberRevisionForm(forms.ModelForm):
    class Meta:
        model = PublisherCodeNumberRevision
        fields = ['number', 'number_type']

    def __init__(self, *args, **kwargs):
        super(PublisherCodeNumberRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.layout = Layout(*(f for f in self.fields))
        if self.instance.id:
            self.fields['number_type'].empty_label = None


PublisherCodeNumberFormSet = inlineformset_factory(
    IssueRevision, PublisherCodeNumberRevision,
    form=PublisherCodeNumberRevisionForm,
    can_delete=True, extra=1)


class IssueRevisionForm(forms.ModelForm):
    class Meta:
        model = IssueRevision
        fields = get_issue_field_list()
        fields.insert(fields.index('year_on_sale'), 'on_sale_date_help')
        fields.insert(fields.index('year_on_sale'), 'on_sale_date')
        fields.insert(fields.index('keywords') + 1, 'turned_off_help')
        widgets = {
            'number': forms.TextInput(attrs={'class': 'wide',
                                             'autofocus': ''}),
            'title': forms.TextInput(attrs={'class': 'wide'}),
            'volume': forms.TextInput(attrs={'class': 'wide'}),
            'publication_date': forms.TextInput(attrs={'class': 'wide'}),
            'key_date': forms.TextInput(attrs={'class': 'key_date'}),
            'indicia_frequency': forms.TextInput(attrs={'class': 'wide'}),
            'price': forms.TextInput(attrs={'class': 'wide'}),
            'editing': forms.TextInput(attrs={'class': 'wide'}),
            'isbn': forms.TextInput(attrs={'class': 'wide'}),
            'barcode': forms.TextInput(attrs={'class': 'wide'}),
            'rating': forms.TextInput(attrs={'class': 'wide'}),
            'page_count': PageCountInput,
            'brand': BrandEmblemSelect,
        }
        labels = ISSUE_LABELS
        help_texts = ISSUE_HELP_TEXTS

    def __init__(self, *args, **kwargs):
        super(IssueRevisionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3 create-label'
        self.helper.field_class = 'col-md-9'
        self.helper.form_tag = False
        fields = list(self.fields)
        credit_start = fields.index('editing')
        field_list = [BaseField(Field(field,
                                      template='oi/bits/uni_field.html'))
                      for field in fields[:credit_start]]
        field_list.append(Formset('credits_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[credit_start:-4]])
        field_list.append(Formset('code_number_formset'))
        field_list.append(Formset('external_link_formset'))
        field_list.extend([BaseField(Field(field,
                                           template='oi/bits/uni_field.html'))
                           for field in fields[-4:]])
        self.helper.layout = Layout(*(f for f in field_list))
        self.helper.doc_links = ISSUE_HELP_LINKS

    indicia_printer = forms.ModelMultipleChoiceField(
        queryset=IndiciaPrinter.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            url='indicia_printer_autocomplete',
            attrs={'style': 'min-width: 60em'}),
        required=False,
        help_text='The exact printer listed in the indicia or colophon, '
                  'if any.'
    )

    comments = _get_comments_form_field()
    turned_off_help = forms.CharField(widget=HiddenInputWithHelp,
                                      required=False)
    on_sale_date_help = forms.CharField(
        widget=HiddenInputWithHelp, required=False, label='',
        help_text='The on-sale (shipping) date can be entered in two ways: '
                  'Either in the next field as YYYY-MM-DD, where all parts '
                  'need to be entered, or using the following three fields. '
                  'If only partial information is known you need to use the '
                  'second option and enter the part of the date which is '
                  'known. If you only know the decade you can enter the '
                  'first three digits, e.g. 199 for the decade 1990-1999.')
    on_sale_date = forms.DateField(required=False, input_formats=['%Y-%m-%d'])


def get_bulk_issue_revision_form(series, method, user=None):
    if method == 'number':
        base = WholeNumberIssueRevisionForm
    elif method == 'volume':
        base = PerVolumeIssueRevisionForm
    elif method == 'year':
        base = PerYearIssueRevisionForm
    elif method == 'year_volume':
        base = PerYearVolumeIssueRevisionForm
    elif method == 'bulk_edit':
        base = BulkEditIssueRevisionForm
    else:
        # TODO: render_error and request are not in scope in this module,
        #       nor were they in the single-file forms module.
        #       Marking this line noqa for flake8 for now.
        return render_error(request,                             # noqa
                            'Unknown method of adding issues.')

    class RuntimeBulkIssueRevisionForm(base):
        class Meta(base.Meta):
            pass

        def __init__(self, *args, **kwargs):
            super(RuntimeBulkIssueRevisionForm, self).__init__(*args, **kwargs)
            self.fields['brand'].queryset = \
                series.publisher.active_brand_emblems_no_pending()
            self.fields['indicia_publisher'].queryset = \
                series.publisher.active_indicia_publishers_no_pending()
            self.fields['no_isbn'].initial = _init_no_isbn(series, None)
            self.fields['no_barcode'].initial = _init_no_barcode(series, None)

        if method != 'bulk_edit':
            if not series.has_indicia_frequency:
                indicia_frequency = forms.CharField(
                    widget=forms.HiddenInput, required=False)
                no_indicia_frequency = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)
            if not series.has_volume:
                volume = forms.CharField(
                    widget=forms.HiddenInput, required=False)
                no_volume = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)
                display_volume_with_number = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)
                volume_not_printed = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)
            if not series.has_isbn:
                no_isbn = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)
            if not series.has_barcode:
                no_barcode = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)
            if not series.has_rating:
                rating = forms.CharField(
                    widget=forms.HiddenInput, required=False)
                no_rating = forms.BooleanField(
                    widget=forms.HiddenInput, required=False)

        after = forms.ModelChoiceField(
            required=False,
            queryset=Issue.objects.exclude(deleted=True)
                                  .filter(series=series)
                                  .order_by('sort_code'),
            empty_label="[add as initial issues]",
            label="Add these issues after")

        def as_table(self):
            if not user or user.indexer.show_wiki_links:
                _set_help_labels(self, ISSUE_HELP_LINKS)
            return super(base, self).as_table()

    return RuntimeBulkIssueRevisionForm


class BulkIssueRevisionForm(forms.ModelForm):
    first_number = forms.IntegerField(
        required=False,
        help_text='If blank, starts with the number after the issue specified '
                  'in the "Add issues after" field, or "1" if '
                  'inserting issues at the beginning')

    number_of_issues = forms.IntegerField(
        min_value=1,
        widget=forms.TextInput(attrs={'autofocus': ''}))

    comments = _get_comments_form_field()

    class Meta:
        model = IssueRevision
        fields = get_issue_field_list()
        exclude = ['number']
        widgets = {
            'indicia_frequency': forms.TextInput(attrs={'class': 'wide'}),
            'editing': forms.TextInput(attrs={'class': 'wide'}),
            'page_count': PageCountInput,
            'brand': BrandEmblemSelect
        }
        labels = ISSUE_LABELS
        help_texts = ISSUE_HELP_TEXTS

    def _shared_key_order(self):
        return ['indicia_publisher', 'indicia_pub_not_printed', 'brand',
                'no_brand', 'indicia_frequency', 'no_indicia_frequency',
                'price', 'page_count', 'page_count_uncertain',
                'editing', 'no_editing', 'no_isbn', 'no_barcode', 'rating',
                'no_rating', 'comments']

    def clean(self):
        cd = self.cleaned_data

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        cd['indicia_frequency'] = cd['indicia_frequency'].strip()
        cd['price'] = cd['price'].strip()
        cd['editing'] = cd['editing'].strip()
        cd['comments'] = cd['comments'].strip()
        if 'volume' in cd:
            cd['volume'] = cd['volume'].strip()

            if cd['volume'] != "" and cd['no_volume']:
                raise forms.ValidationError(
                    'You cannot specify a volume and '
                    'check "no volume" at the same time')

        if cd['editing'] != "" and cd['no_editing']:
            raise forms.ValidationError(
                'You cannot specify an editing credit and '
                'check "no editing" at the same time')

        if cd['no_brand'] and cd['brand'] is not None:
            raise forms.ValidationError(
                ['Brand field and No Brand checkbox cannot both be filled in.']
            )

        if cd['no_indicia_frequency'] and cd['indicia_frequency']:
            raise forms.ValidationError(
                ['Indicica Frequency field and No Indicia Frequency checkbox '
                 'cannot both be filled in.'])

        if 'rating' in cd:
            cd['rating'] = cd['rating'].strip()

            if cd['rating'] != "" and cd['no_rating']:
                raise forms.ValidationError(
                    'You cannot specify a rating and '
                    'check "no rating" at the same time')

        return cd


class BulkEditIssueRevisionForm(BulkIssueRevisionForm):
    def __init__(self, *args, **kwargs):
        super(BulkEditIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['no_title', 'volume', 'display_volume_with_number',
                    'no_volume', 'volume_not_printed']
        ordering.extend(self._shared_key_order())
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields


class WholeNumberIssueRevisionForm(BulkIssueRevisionForm):

    def __init__(self, *args, **kwargs):
        super(WholeNumberIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'volume', 'display_volume_with_number', 'no_volume']
        ordering.extend(self._shared_key_order())
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    def clean(self):
        cd = super(WholeNumberIssueRevisionForm, self).clean()

        if cd['first_number'] is None and cd['after'] is not None:
            try:
                cd['first_number'] = int(cd['after'].number) + 1
            except ValueError:
                raise forms.ValidationError(
                    'When adding new issues following  an '
                    'existing issue, the issue after which you are adding the '
                    'new issues must have a whole number as the issue number')
        elif cd['first_number'] is None:
            cd['first_number'] = 1

        return cd


class PerVolumeIssueRevisionForm(BulkIssueRevisionForm):
    first_volume = forms.IntegerField(
        required=False,
        help_text='If blank, first volume is calculated from the issue '
                  'specified in the "Add issues after" field, or "1" if '
                  'inserting at the beginning. Only numeric volumes allowed.')

    issues_per_volume = forms.IntegerField(
        min_value=1, initial=12,
        help_text='Number of issues in each volume')

    def __init__(self, *args, **kwargs):
        super(PerVolumeIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues', 'first_number',
                    'first_volume', 'issues_per_volume']
        ordering.extend(self._shared_key_order())
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    def clean(self):
        cd = super(PerVolumeIssueRevisionForm, self).clean()

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        basics = (cd['first_number'], cd['first_volume'])
        if None in basics and cd['after'] is not None:
            if [x for x in basics if x is not None]:
                raise forms.ValidationError(
                    'When adding issues following an existing issue, both '
                    'of "first number" and "first volume" must be specified, '
                    'or both must be left blank.')

        if cd['first_number'] is None and cd['after'] is not None:
            try:
                cd['first_number'] = ((int(cd['after'].number) + 1) %
                                      cd['issues_per_volume'])
                if cd['first_number'] == 0:
                    cd['first_number'] = cd['issues_per_volume']
            except ValueError:
                raise forms.ValidationError(
                    'When adding issues following an existing issue, the '
                    'issue after which you are inserting the new issues must '
                    'have a whole number for the issue number (even if it '
                    'displays like "v1#1")')

            if cd['after'].volume is None:
                raise forms.ValidationError(
                    'When adding issues following an existing issue, the '
                    'issue after which you are inserting the new issues '
                    'must have a volume.')

            cd['first_volume'] = cd['after'].volume
            if cd['first_number'] == 1:
                cd['first_volume'] += 1

        elif cd['after'] is None:
            if cd['first_number'] is None:
                cd['first_number'] = 1
            if cd['first_volume'] is None:
                cd['first_volume'] = 1

        return cd


class PerYearIssueRevisionForm(BulkIssueRevisionForm):
    first_number = forms.IntegerField(
        required=False,
        help_text='First issue number (the portion before the "/").  '
                  'If blank, starts with the number after the issue '
                  'specified in the "Add issues after" field, or "1" if '
                  'inserting issues at the beginning.')
    first_year = forms.IntegerField(
        required=False,
        help_text='If blank, first year is calculated from the issue '
                  'specified in the "Add issues after" field.  If '
                  'inserting at the beginning of the series, this field '
                  'is required')

    issues_per_year = forms.IntegerField(
        min_value=1, initial=12,
        help_text='Number of issues in each year')

    def __init__(self, *args, **kwargs):
        super(PerYearIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues',
                    'first_number', 'first_year', 'issues_per_year',
                    'volume', 'display_volume_with_number', 'no_volume']
        ordering.extend(self._shared_key_order())
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    def clean(self):
        cd = super(PerYearIssueRevisionForm, self).clean()

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        basics = (cd['first_number'], cd['first_year'])
        if None in basics and cd['after'] is not None:
            if [x for x in basics if x is not None]:
                raise forms.ValidationError(
                    'When adding issues following an existing issue, '
                    'both of "first number" and "first year" must be '
                    'specified, or both must be left blank.')

        if cd['after'] is None and cd['first_year'] is None:
            raise forms.ValidationError(
                'When inserting issues at the beginning '
                'of a series, the first year must be specified.')

        if cd['first_number'] is None and cd['after'] is not None:
            cd = self._parse_year_and_number(cd, cd['issues_per_year'])
        elif cd['first_number'] is None:
            cd['first_number'] = 1

        return cd

    def _parse_year_and_number(self, cd, issues_per):
        previous = cd['after'].number
        m = re.match(r'(?P<number>\d+)/(?P<year>\d+)', previous)
        if m is None:
            raise forms.ValidationError(
                'When adding based on the number of a previous issue, '
                'the issue must start with a number, then a forward slash, '
                'then a year, with no spaces: 1/1975')
        cd['first_number'] = ((int(m.group('number')) + 1) %
                              issues_per)
        if cd['first_number'] == 0:
            cd['first_number'] = issues_per

        cd['first_year'] = int(m.group('year'))
        if cd['first_number'] == 1:
            cd['first_year'] += 1
        return cd


class PerYearVolumeIssueRevisionForm(PerYearIssueRevisionForm):
    first_volume = forms.IntegerField(
        required=False,
        help_text='If blank, first volume is calculated from the issue '
                  'specified in the "Add issues after" field, or "1" if '
                  'inserting at the beginning. Only numeric volumes allowed.')

    issues_per_cycle = forms.IntegerField(
        min_value=1, initial=12,
        help_text='Number of issues in each year/volume')

    def __init__(self, *args, **kwargs):
        super(PerYearIssueRevisionForm, self).__init__(*args, **kwargs)
        ordering = ['after', 'number_of_issues',
                    'first_number', 'first_year', 'first_volume',
                    'issues_per_cycle', 'display_volume_with_number']
        ordering.extend(self._shared_key_order())
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    def clean(self):
        cd = super(PerYearIssueRevisionForm, self).clean()

        if self._errors:
            raise forms.ValidationError(GENERIC_ERROR_MESSAGE)

        basics = (cd['first_number'], cd['first_volume'], cd['first_year'])
        if None in basics and cd['after'] is not None:
            if [x for x in basics if x is not None]:
                raise forms.ValidationError(
                    'When adding issues following an existing issue, all '
                    'of "first number", "first volume" and "first year" must '
                    'be specified, or all must be left blank.')
        if cd['after'] is None and cd['first_year'] is None:
            raise forms.ValidationError(
                'When inserting issues at the beginning '
                'of a series, the first year must be specified.')

        if cd['first_number'] is None and cd['after'] is not None:
            cd = self._parse_year_and_number(cd, cd['issues_per_cycle'])
            if cd['after'].volume is None:
                raise forms.ValidationError(
                    'When adding issues following an existing issue, '
                    'the issue after which you are inserting '
                    'the new issues must have a volume.')
            cd['first_volume'] = cd['after'].volume
            if cd['first_number'] == 1:
                cd['first_volume'] += 1

        elif cd['after'] is None:
            if cd['first_number'] is None:
                cd['first_number'] = 1
            if cd['first_volume'] is None:
                cd['first_volume'] = 1

        return cd
