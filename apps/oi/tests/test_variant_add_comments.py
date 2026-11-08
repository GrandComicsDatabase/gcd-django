import pytest

from django.contrib.auth.models import Permission
from django.http import QueryDict
from django.urls import reverse

from apps.oi import states
from apps.oi.forms import (get_revision_form, IssueRevisionFormSet,
                           ExternalLinkRevisionFormSet,
                           PublisherCodeNumberFormSet)
from apps.oi.models import Changeset, CTYPES
from apps.oi.views import (_add_form_data, _add_formset_data,
                           init_added_variant)

COMMENT = 'Variant has a different price, see indicia scan.'


def _variant_add_form_data(base_issue, user):
    """The data of the add variant form, as a browser sends it."""
    series = base_issue.series
    form_class = get_revision_form(model_name='issue', series=series,
                                   publisher=series.publisher,
                                   variant_of=base_issue, user=user)
    form = init_added_variant(form_class, dict(base_issue.__dict__),
                              base_issue)
    data = QueryDict('', mutable=True)
    _add_form_data(data, form)
    formsets = [IssueRevisionFormSet(), ExternalLinkRevisionFormSet()]
    if series.has_publisher_code_number:
        formsets.append(PublisherCodeNumberFormSet())
    for formset in formsets:
        _add_formset_data(data, formset)
    data['variant_name'] = 'Test Variant'
    data['comments'] = COMMENT
    return data


@pytest.mark.django_db
@pytest.mark.parametrize('path', ['submit', 'edit_with_base',
                                  'add_to_issue_revision'])
def test_variant_add_keeps_comment(client, any_indexer, any_added_issue,
                                   path):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    data = _variant_add_form_data(any_added_issue, any_indexer)

    if path == 'add_to_issue_revision':
        client.post(reverse('reserve_revision',
                            kwargs={'model_name': 'issue',
                                    'id': any_added_issue.id}))
        changeset = Changeset.objects.get(indexer=any_indexer,
                                          state=states.OPEN)
        url = reverse('add_variant_to_issue_revision',
                      kwargs={'changeset_id': changeset.id,
                              'issue_revision_id':
                              changeset.issuerevisions.get().id})
    else:
        if path == 'edit_with_base':
            data['edit_with_base'] = 'Save New Variant Issue And Edit Both'
        url = reverse('add_variant_issue',
                      kwargs={'issue_id': any_added_issue.id})
    client.post(url, data)

    changeset = Changeset.objects.get(indexer=any_indexer,
                                      state=states.OPEN)
    assert changeset.issuerevisions.filter(
      variant_of=any_added_issue, issue=None).exists()
    assert COMMENT in changeset.comments.values_list('text', flat=True)
