"""
Check a revision with the rules of its edit form, without a request.

The submit view runs these checks on the saved values of a change, and a
bulk change on each object that it changes.  This module must not import
apps.oi.views.
"""
from django.forms import CheckboxInput, FileField, ModelChoiceField
from django.http import QueryDict

from apps.oi.forms import get_revision_form


class _FormRequest:
    """The parts of a request that the extra forms of a revision read."""

    def __init__(self, user, data):
        self.user = user
        self.POST = data


def _value_for_post(value):
    """Return value as a browser would post it: an object as its id."""
    if hasattr(value, 'pk'):
        return value.pk
    return value


def _add_form_data(data, form):
    """Serialize an unbound form's current values as browser-like POST data."""
    for name, field in form.fields.items():
        if isinstance(field, FileField):
            # Omitting a file input preserves the file already on the instance.
            continue

        key = form.add_prefix(name)
        value = form[name].value()

        # A select without an empty choice submits its first option even when
        # the unbound BoundField has no explicit initial value.
        if value is None and isinstance(field, ModelChoiceField) and \
           not getattr(field.widget, 'allow_multiple_selected', False) and \
           field.empty_label is None:
            first_choice = field.queryset.first()
            if first_choice is not None:
                value = first_choice.pk

        if getattr(field.widget, 'allow_multiple_selected', False) or \
           isinstance(value, (list, tuple)) or hasattr(value, 'all'):
            # An empty multi-select is omitted from browser POST data; posting
            # one empty value makes Django reject it as an invalid choice.
            if value is None or value == '':
                values = []
            elif hasattr(value, 'all'):
                values = value.all()
            elif isinstance(value, (list, tuple)):
                values = value
            else:
                values = [value]
            data.setlist(key, [str(_value_for_post(item))
                               for item in values])
        elif isinstance(field.widget, CheckboxInput):
            if value:
                data[key] = 'on'
        else:
            value = _value_for_post(value)
            data[key] = '' if value is None else str(value)


def _add_formset_data(data, formset):
    """Serialize an unbound formset, management form included."""
    prefix = formset.prefix
    data['%s-TOTAL_FORMS' % prefix] = str(formset.total_form_count())
    data['%s-INITIAL_FORMS' % prefix] = str(formset.initial_form_count())
    data['%s-MIN_NUM_FORMS' % prefix] = str(formset.min_num)
    data['%s-MAX_NUM_FORMS' % prefix] = str(formset.max_num)
    for form in formset.forms:
        _add_form_data(data, form)


def _validation_messages(form, extra_forms):
    """Return the error messages of form and extra_forms, without repeats."""
    messages = []
    for errors in form.errors.values():
        messages.extend(str(error) for error in errors)
    for formset in extra_forms.values():
        if formset is None:
            continue
        for errors in formset.errors:
            for field_errors in errors.values():
                messages.extend(str(error) for error in field_errors)
        messages.extend(str(error) for error in formset.non_form_errors())
    return list(dict.fromkeys(messages))


def revision_form_messages(revision, user, dependents=True, original=None):
    """
    Return the error messages that the edit form of revision and its
    formsets give for the values of revision, as if user saved its edit
    page unchanged; an empty list if it passes.

    The values are those of the instance, saved or not, and of its saved
    dependent revisions.  With dependents False the formsets are left
    out, which is how a new revision without dependents is checked.  As
    with any model form, the check sets the cleaned values of the form
    fields on revision, without saving them.

    original, when given, is revision as it was before the values under
    check were set on it.  The edit form then takes its choices from
    original, as the edit page of the revision would, so that a new value
    gets no exception that only the value a revision holds has.
    """
    form_class = get_revision_form(
      revision if original is None else original, user=user)
    unbound_form = form_class(instance=revision)
    unbound_extra_forms = {}
    if dependents:
        unbound_extra_forms = revision.extra_forms(
          _FormRequest(user, QueryDict()))

    data = QueryDict('', mutable=True)
    _add_form_data(data, unbound_form)
    for formset in unbound_extra_forms.values():
        if formset is not None:
            _add_formset_data(data, formset)

    form = form_class(data, instance=revision)
    extra_forms = {}
    if dependents:
        extra_forms = revision.extra_forms(_FormRequest(user, data))

    # Evaluate every formset even if the main form fails so the indexer sees
    # all persisted-data errors in one pass.
    valid = form.is_valid()
    for formset in extra_forms.values():
        if formset is not None:
            if not formset.is_valid():
                valid = False

    if valid:
        return []
    return _validation_messages(form, extra_forms)
