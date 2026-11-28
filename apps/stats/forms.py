# -*- coding: utf-8 -*-


from django import forms
from django.utils.translation import gettext_lazy as _


class DownloadForm(forms.Form):
    """ Form for downloading data dumps. """

    purpose = forms.ChoiceField(
        required=False,
        widget=forms.RadioSelect,
        choices=(('private', _('Private use')),
                 ('non-commercial', _('Public / Non-Commercial use')),
                 ('commercial', _('Public / Commercial use'))),
        label=_("[Optional] Purpose:"))

    usage = forms.CharField(
        required=False,
        widget=forms.Textarea,
        label=_("[Optional] How or where do you plan to use the data?"))

    # Set required=False so we can supply a better error message.
    accept_license = forms.BooleanField(
        required=False,
        label=_('I have read and accept the GCD data licensing terms and '
                'crediting guidelines'))

    def clean(self):
        cd = self.cleaned_data
        cd['usage'] = cd['usage'].strip()

        if cd['accept_license'] is not True:
            raise forms.ValidationError(
                _('You must check the box indicating your acceptance of the '
                  'licensing and crediting terms in order to download the '
                  'data.'))

        return cd
