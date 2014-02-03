from django import forms

def get_generic_select_form(choices):

    class GenericSelectForm(forms.Form):
        object_choice = forms.ChoiceField(choices=choices, label='')
    return GenericSelectForm