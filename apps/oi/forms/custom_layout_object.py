from django.template.loader import render_to_string

from crispy_forms.bootstrap import TabHolder
from crispy_forms.layout import LayoutObject
from crispy_forms.layout import Field
from crispy_forms.utils import render_field

# from:
# ###### https://stackoverflow.com/questions/15157262/django-crispy-forms-nesting-a-formset-within-a-form/22053952#22053952

class BaseField(Field):
    def render(self, form, context, template_pack=None):
        fields = ''

        for field in self.fields:
            fields += render_field(field, form, context,
                                   template_pack=template_pack)
        return fields


class FormAsField(LayoutObject):
    """
    Renders an entire form, as though it were a Field.
    Accepts the names (as a string) of form and helper as they
    are defined in the context

    Examples:
        FormAsField('contact_form')
        FormAsField('contact_form', 'contact_form_helper')
    """

    template = "oi/bits/form_as_field.html"

    def __init__(self, form_context_name, helper_context_name=None,
                 template=None, label=None):

        self.form_context_name = form_context_name
        self.helper_context_name = helper_context_name

        # crispy_forms/layout.py:302 requires us to have a fields property
        self.fields = []

        # Overrides class variable with an instance level variable
        if template:
            self.template = template

    def render(self, form, context, renderer=None, **kwargs):
        form = context.get(self.form_context_name)
        helper = context.get(self.helper_context_name)
        # closes form prematurely if this isn't explicitly stated
        if helper:
            helper.form_tag = False

        context.update({'form': form, 'helper': helper})
        return render_to_string(self.template, context.flatten())


class Formset(LayoutObject):
    """
    Renders an entire formset, as though it were a Field.
    Accepts the names (as a string) of formset and helper as they
    are defined in the context

    Examples:
        Formset('contact_formset')
        Formset('contact_formset', 'contact_formset_helper')
    """

    template = "oi/bits/formset.html"

    def __init__(self, formset_context_name, helper_context_name=None,
                 template=None, label=None):

        self.formset_context_name = formset_context_name
        self.helper_context_name = helper_context_name

        # crispy_forms/layout.py:302 requires us to have a fields property
        self.fields = []

        # Overrides class variable with an instance level variable
        if template:
            self.template = template

    def render(self, form, context, renderer=None, **kwargs):
        formset = context.get(self.formset_context_name)
        helper = context.get(self.helper_context_name)
        # closes form prematurely if this isn't explicitly stated
        if helper:
            helper.form_tag = False

        context.update({'formset': formset, 'helper': helper})
        return render_to_string(self.template, context.flatten())

    def has_errors(self, context):
        formset = context.get(self.formset_context_name)
        return formset is not None and formset.total_error_count() > 0


class FormsetTabHolder(TabHolder):
    """
    Opens the first tab with errors, also looking at the formsets of a tab.

    The formsets are not fields of the form, so TabHolder does not know
    about their errors when it selects the tab to open.
    """

    def render(self, form, context, *args, **kwargs):
        self.tabs_with_formset_errors = [
          tab for tab in self.fields
          if any(isinstance(field, Formset) and field.has_errors(context)
                 for field in tab.fields)]
        return super().render(form, context, *args, **kwargs)

    def first_container_with_errors(self, errors):
        for tab in self.fields:
            if tab in self.tabs_with_formset_errors or \
               any(error in tab for error in errors):
                return tab
        return None
