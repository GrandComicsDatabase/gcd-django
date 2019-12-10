# -*- coding: utf-8 -*-


from collections import OrderedDict

from django import forms
from django.core import urlresolvers

from apps.oi.models import CoverRevision, ImageRevision

from .support import _get_comments_form_field, HiddenInputWithHelp


def get_cover_revision_form(revision=None, user=None):
    compare_url = '<a href="' + urlresolvers.reverse(
        'compare',
        kwargs={'id': revision.changeset.id}) + '">Compare Change</a>'

    # TODO Revisit this. Does it need to be a ModelForm to be consistent
    # to other forms which get returned by get_revision_form, or can
    # this be a normal Form and avoid the slight hackish way of not
    # really using the ModelForm before in the actual cover upload.
    class UploadScanCommentForm(forms.ModelForm):
        class Meta:
            model = CoverRevision
            fields = []

        comments = forms.CharField(
            widget=forms.Textarea,
            required=False,
            help_text='Comments between the Indexer and Editor about '
                      'the change. These comments are part of the public '
                      'change history, but are not part of the regular '
                      'display. <p>%s</p>' % compare_url)

        def clean(self):
            cd = self.cleaned_data
            cd['comments'] = cd['comments'].strip()
            return cd

    return UploadScanCommentForm


class UploadScanForm(forms.Form):
    """ Form for cover uploads. """

    scan = forms.ImageField(widget=forms.FileInput)
    source = forms.CharField(
        label='Source',
        required=True,
        help_text='If you upload a scan from another website, make sure you '
                  'have permission to do that and mention the source. If you '
                  'upload on behalf of someone else you can mention this here '
                  'as well. Otherwise, indicate that you scanned it yourself.')
    remember_source = forms.BooleanField(
        label='Remember the source',
        required=False,
        help_text="Tick only if you do multiple uploads from the source.")
    marked = forms.BooleanField(
        label="Mark cover for replacement",
        required=False,
        help_text='Uploads of sub-standard scans for older and/or rare '
                  'comics are fine, but please mark them for replacement.')
    is_wraparound = forms.BooleanField(
        label="Wraparound cover",
        required=False,
        help_text='Cover is a standard wraparound cover: Two pages in width, '
                  'the right half is the front cover and will be '
                  'automatically selected.')
    is_gatefold = forms.BooleanField(
        label="Gatefold cover",
        required=False,
        help_text='Cover is a non-standard wraparound cover or a gatefold '
                  'cover. After the upload you will select the front cover '
                  'part. The selection will not work if JavaScript is '
                  'turned off.')
    comments = _get_comments_form_field()

    def clean(self):
        cd = self.cleaned_data
        if 'source' in cd:
            cd['source'] = cd['source'].strip()
        cd['comments'] = cd['comments'].strip()
        if cd['is_wraparound'] and cd['is_gatefold']:
            raise forms.ValidationError(
                ['Wraparound cover and gatefold cover cannot be both '
                 'selected. A cover that is both wraparound and gatefold '
                 'should be submitted as a gatefold cover.'])
        return cd


class UploadVariantScanForm(UploadScanForm):
    def __init__(self, *args, **kwargs):
        super(UploadVariantScanForm, self).__init__(*args, **kwargs)
        ordering = list(self.fields.keys())
        ordering.remove('variant_name')
        ordering.remove('variant_artwork')
        ordering.remove('reservation_requested')
        ordering = ['variant_artwork'] + ordering
        ordering = ['variant_name'] + ordering
        ordering = ['reservation_requested'] + ordering
        new_fields = OrderedDict([(f, self.fields[f]) for f in ordering])
        self.fields = new_fields

    is_gatefold = forms.CharField(
        widget=HiddenInputWithHelp,
        required=False,
        label="Gatefold cover",
        help_text='Gatefold uploads are currently not supported when '
                  'creating a variant with a cover image upload. Please '
                  'first create the variant issue before uploading a '
                  'gatefold cover.')
    variant_name = forms.CharField(
        required=False,
        help_text='Name of this variant. Examples are: "Cover A" (if '
                  'listed as such in the issue), "second printing", '
                  '"newsstand", "direct", or the name of the artist if '
                  'different from the base issue.')
    variant_artwork = forms.BooleanField(
        required=False,
        initial=True,
        label='Variant artwork',
        help_text='Check this box if the uploaded variant cover has artwork '
                  'different from the base issue. If checked a cover '
                  'sequence will be generated with question marks in the '
                  'creator fields on approval.')
    reservation_requested = forms.BooleanField(
        required=False,
        label='Request variant reservation',
        help_text='Ideally you request a reservation for the new variant to '
                  'later fill in the missing data. Check this box to have the '
                  'variant issue reserved to you automatically when it is '
                  'approved.')


class GatefoldScanForm(forms.Form):
    """ Form for cover uploads. """

    left = forms.IntegerField(widget=forms.TextInput(attrs={'size': '4'}))
    width = forms.IntegerField(widget=forms.TextInput(attrs={'size': '4'}))
    real_width = forms.IntegerField(widget=forms.HiddenInput)
    top = forms.IntegerField(widget=forms.TextInput(attrs={'size': '4'}))
    height = forms.IntegerField(widget=forms.TextInput(attrs={'size': '4'}))
    cover_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    issue_id = forms.IntegerField(widget=forms.HiddenInput)
    scan_name = forms.CharField(widget=forms.HiddenInput)
    source = forms.CharField(widget=forms.HiddenInput, required=False)
    remember_source = forms.BooleanField(widget=forms.HiddenInput,
                                         required=False)
    marked = forms.BooleanField(widget=forms.HiddenInput, required=False)
    comments = forms.CharField(widget=forms.HiddenInput, required=False)


class UploadImageForm(forms.Form):
    """ Form for image uploads. """
    class Meta:
        model = ImageRevision

    image = forms.ImageField(widget=forms.FileInput)

    marked = forms.BooleanField(
        label="Mark image for replacement",
        required=False,
        help_text='Uploads of sub-standard images for older and/or rare '
                  'comics are fine, but please mark them for replacement.')

    comments = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label='Source / Comments',
        help_text='Please credit the source of this image if scanned or '
                  'otherwise provided by another site or person, along with '
                  'any additional comments to the upload approver.')
