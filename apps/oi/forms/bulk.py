"""
The form of a bulk change: one operation on one field of many objects.
"""
import copy

from django import forms
from django.db import models

from apps.gcd.templatetags.display import field_name
from apps.oi import bulk
from apps.oi.forms.issue import IssueRevisionForm
from apps.oi.forms.series import SeriesRevisionForm
from apps.oi.forms.support import _strip_list
from apps.oi.models import IssueRevision, SeriesRevision

# The edit form of each revision class: the order of the fields and the
# field of the new value.
REVISION_FORMS = {IssueRevision: IssueRevisionForm,
                  SeriesRevision: SeriesRevisionForm}


def offered_fields(rev_class, publisher):
    """
    Return the fields of rev_class that a bulk change offers, in the order
    of the edit form; a link field only if the objects have one publisher.
    """
    natures = bulk.policy_fields(rev_class)
    return [name for name in REVISION_FORMS[rev_class].base_fields
            if name in natures and (publisher or natures[name] != 'L')]


# The fields whose value the clean method of the edit form strips as a
# list: spaces and a ';' at the end go.
STRIPPED_AS_LISTS = ('price',)


class BulkOperationForm(forms.Form):
    """
    The operation of a bulk change on the field name, chosen with GET.

    The old value is one of values, the (value, count) pairs of the field
    among the selected objects.  The new value goes in a copy of the field
    of the edit form, not required, and is cleaned as there, so that the
    preview shows the value that is stored; the rules of the whole edit
    form apply to each object when the change is applied.  shown holds
    the field whose values the page lists: the page binds the form only
    if it is still the chosen field.
    """
    field = forms.ChoiceField()
    shown = forms.CharField(widget=forms.HiddenInput)
    old_value = forms.ChoiceField(widget=forms.RadioSelect, required=False)
    operation = forms.ChoiceField()

    def __init__(self, data, rev_class, name, values, publisher):
        super().__init__(data, initial={'field': name, 'shown': name})
        self.name = name
        self.edit_form_class = REVISION_FORMS[rev_class]
        self.model_field = rev_class._meta.get_field(name)
        self.field_label = field_name(name)
        self.values = {bulk.value_key(value): value
                       for value, count in values}
        self.fields['field'].choices = [
          (field, field_name(field))
          for field in offered_fields(rev_class, publisher)]
        self.fields['old_value'].choices = bulk.value_choices(
          rev_class._meta.get_field(name), values)
        operations = bulk.operations(
          name, bulk.policy_fields(rev_class)[name])
        self.fields['operation'].choices = operations
        if len(operations) > 1:
            self.fields['old_value'].help_text = \
                'Used only with Replace the old value.'

        new_value = copy.deepcopy(self.edit_form_class.base_fields[name])
        new_value.label = 'New value'
        new_value.required = False
        if name == 'indicia_publisher':
            # The edit form lists the indicia publishers of the publisher.
            new_value.queryset = \
                publisher.active_indicia_publishers_no_pending()
        self.fields['new_value'] = new_value

    def clean_new_value(self):
        """
        Return the new value as the edit form stores it: after its field,
        the clean method of the edit form for the field, if any, as for
        the dashes of a key date, the strip of a list that its clean
        method makes, as for a ';' at the end of a price, and the
        validators of the model field, as for the pattern of a key date;
        a linked object as its id.
        """
        value = self.cleaned_data['new_value']
        if hasattr(self.edit_form_class, 'clean_' + self.name):
            edit_form = self.edit_form_class()
            edit_form.cleaned_data = {self.name: value}
            value = getattr(edit_form, 'clean_' + self.name)()
        if self.name in STRIPPED_AS_LISTS:
            value = _strip_list(value)
        self.model_field.run_validators(value)
        if isinstance(value, models.Model):
            return value.pk
        return value

    def clean(self):
        """
        Turn the chosen old value into the stored value, which replacing
        needs, and keep the fields of bulk.NOT_EMPTY from being emptied or
        filled where empty.
        """
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        key = cleaned_data['old_value']
        if cleaned_data['operation'] == 'replace_exact' and not key:
            raise forms.ValidationError('Please choose the old value.')
        cleaned_data['old_value'] = self.values.get(key)
        if self.name in bulk.NOT_EMPTY and not cleaned_data['old_value']:
            raise forms.ValidationError(
              'The old value of %s cannot be empty.' % self.field_label)
        if self.name in bulk.NOT_EMPTY and \
           cleaned_data['new_value'] in ('', None):
            raise forms.ValidationError(
              'The new value of %s cannot be empty.' % self.field_label)
        return cleaned_data
