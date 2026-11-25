import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.oi.import_export import BRAND, INDICIA_PUBLISHER, ISSUE_NOTES, \
                                  NUMBER, ON_SALE_DATE
from apps.oi.models import IssueRevision


@pytest.fixture
def logged_in(client, any_indexer):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)


def _issue_line(client, revision):
    response = client.get(reverse('export_issue_revision',
                                  kwargs={'issue_id': revision.id}))
    assert response.status_code == 200
    return response.content.decode().split('\r\n')[0].split('\t')


@pytest.mark.django_db
def test_a_downloaded_revision_has_the_values_of_the_revision(
  client, logged_in, any_added_issue, any_editing_changeset):
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=any_editing_changeset)
    revision.notes = 'Notes of the revision'
    revision.save()

    issue_line = _issue_line(client, revision)

    assert issue_line[NUMBER] == any_added_issue.number
    assert issue_line[BRAND] == any_added_issue.brand_emblem.get().name
    assert issue_line[INDICIA_PUBLISHER] == (
      any_added_issue.indicia_publisher.name)
    assert issue_line[ISSUE_NOTES] == 'Notes of the revision'
    # the on-sale date of the fixture is uncertain
    assert issue_line[ON_SALE_DATE] == '1946-11-23?'


@pytest.mark.django_db
def test_a_downloaded_revision_has_its_own_on_sale_date_certainty(
  client, logged_in, any_added_issue, any_editing_changeset):
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=any_editing_changeset)
    revision.on_sale_date_uncertain = False
    revision.save()

    assert _issue_line(client, revision)[ON_SALE_DATE] == '1946-11-23'


@pytest.mark.django_db
def test_an_issue_being_added_can_be_downloaded(client, logged_in,
                                                any_added_issue_rev):
    assert _issue_line(client, any_added_issue_rev)[NUMBER] == '42'
