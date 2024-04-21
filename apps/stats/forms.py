# -*- coding: utf-8 -*-


from django import forms


class DownloadForm(forms.Form):
    """ Form for downloading data dumps. """

    purpose = forms.ChoiceField(
        required=False,
        widget=forms.RadioSelect,
        choices=(('private', 'Private use'),
                 ('non-commercial', 'Public / Non-Commercial use'),
                 ('commercial', 'Public / Commercial use')),
        label="[Optional] Purpose:")

    usage = forms.CharField(
        required=False,
        widget=forms.Textarea,
        label="[Optional] How or where do you plan to use the data?")

    # Set required=False so we can supply a better error message.
    accept_license = forms.BooleanField(
        required=False,
        label='I have read and accept the GCD data licensing terms and '
              'crediting guidelines')

    def clean(self):
        cd = self.cleaned_data
        cd['usage'] = cd['usage'].strip()

        if cd['accept_license'] is not True:
            raise forms.ValidationError(
                'You must check the box indicating your acceptance of the '
                'licensing and crediting terms in order to download the data.')

        return cd
