import pytest

from django.forms import CheckboxInput
from django.http import QueryDict

from apps.oi.forms.creator import get_creator_non_comic_work_revision_form
from apps.oi.forms.issue import get_issue_revision_form
from apps.oi.forms.story import get_story_revision_form
from apps.oi.models import IssueRevision


def _post_data(form):
    """The data a browser sends when the edit page is saved unchanged."""
    data = QueryDict(mutable=True)
    for bound_field in form:
        value = bound_field.value()
        if isinstance(bound_field.field.widget, CheckboxInput):
            if value:
                data[bound_field.html_name] = 'on'
        elif isinstance(value, (list, tuple)):
            data.setlist(bound_field.html_name, [str(v) for v in value])
        elif value is not None:
            data[bound_field.html_name] = str(value)
    return data


@pytest.mark.django_db
@pytest.mark.parametrize('field', [
    'feature', 'script', 'pencils', 'inks', 'colors', 'letters', 'editing',
    'characters', 'reprint_notes'])
def test_story_form_strips_trailing_semicolon(any_edit_story_rev,
                                              any_indexer, field):
    form_class = get_story_revision_form(revision=any_edit_story_rev,
                                         user=any_indexer)
    data = _post_data(form_class(instance=any_edit_story_rev))
    data['story_credit_revisions-TOTAL_FORMS'] = '0'
    data.pop('no_%s' % field, None)
    data[field] = 'Asdf; Qwer; '

    form = form_class(data, instance=any_edit_story_rev)

    assert form.is_valid(), form.errors
    assert form.cleaned_data[field] == 'Asdf; Qwer'


@pytest.mark.django_db
@pytest.mark.parametrize('field, value, expected', [
    ('price', '0.10 USD; 0.15 CAD;', '0.10 USD; 0.15 CAD'),
    ('editing', 'Asdf; Qwer;', 'Asdf; Qwer'),
    ('isbn', '9780307290632; 0307290638;', '9780307290632; 0307290638'),
    ('barcode', '012345678905; 012345678912;',
     '012345678905; 012345678912')])
def test_issue_form_strips_trailing_semicolon(
        any_added_issue, any_editing_changeset, any_indexer,
        field, value, expected):
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=any_editing_changeset)
    form_class = get_issue_revision_form(
      publisher=any_added_issue.series.publisher, revision=revision,
      user=any_indexer)
    data = _post_data(form_class(instance=revision))
    data.pop('no_%s' % field, None)
    data[field] = value

    form = form_class(data, instance=revision)

    assert form.is_valid(), form.errors
    assert form.cleaned_data[field] == expected


def test_creator_work_years_strips_trailing_semicolon():
    form = get_creator_non_comic_work_revision_form()(
      data={'work_years': '1990; 1991;'})
    form.is_valid()

    assert 'work_years' not in form.errors
    assert form.cleaned_data['work_years'] == '1990; 1991'
