"""Validate persisted revisions before changeset workflow transitions."""

from copy import copy

from django.forms import CheckboxInput, FileField, ModelChoiceField
from django.http import QueryDict

from apps.oi.forms import get_revision_form


def _value_for_post(value):
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
    prefix = formset.prefix
    data['%s-TOTAL_FORMS' % prefix] = str(formset.total_form_count())
    data['%s-INITIAL_FORMS' % prefix] = str(formset.initial_form_count())
    data['%s-MIN_NUM_FORMS' % prefix] = str(formset.min_num)
    data['%s-MAX_NUM_FORMS' % prefix] = str(formset.max_num)
    for form in formset.forms:
        _add_form_data(data, form)


def _validation_messages(form, extra_forms):
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


def validate_revision_for_transition(revision, request):
    """Run the editing form and formset validators against saved values."""
    # extra_forms() reads request.POST, so use request copies rather than
    # replacing the data submitted to the workflow action itself.
    unbound_request = copy(request)
    unbound_request.POST = QueryDict()

    form_class = get_revision_form(revision, user=request.user)
    unbound_form = form_class(instance=revision)
    unbound_extra_forms = revision.extra_forms(unbound_request)

    data = QueryDict('', mutable=True)
    _add_form_data(data, unbound_form)
    for formset in unbound_extra_forms.values():
        if formset is not None:
            _add_formset_data(data, formset)

    bound_request = copy(request)
    bound_request.POST = data
    form = form_class(data, instance=revision)
    extra_forms = revision.extra_forms(bound_request)

    # Evaluate every formset even if the main form fails so the indexer sees
    # all persisted-data errors in one pass.
    valid = form.is_valid()
    for formset in extra_forms.values():
        if formset is not None:
            valid = formset.is_valid() and valid

    if valid:
        return []
    return _validation_messages(form, extra_forms)


def validate_changeset_revisions(changeset, request):
    """Return invalid active issue/story revisions and their errors."""
    invalid = []
    revisions = list(changeset.issuerevisions.filter(deleted=False))
    revisions.extend(changeset.storyrevisions.filter(deleted=False))
    for revision in revisions:
        messages = validate_revision_for_transition(revision, request)
        if messages:
            invalid.append((revision, messages))
    return invalid
