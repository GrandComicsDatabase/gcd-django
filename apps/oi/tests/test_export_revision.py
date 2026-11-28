import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.oi.interchange import YES, parse_items
from apps.oi.models import IssueRevision


@pytest.fixture
def logged_in(client, any_indexer):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)


def _issue_line(client, revision):
    """
    The issue line of the downloaded TSV file, by column name.
    """
    response = client.get(reverse('export_issue_revision',
                                  kwargs={'issue_id': revision.id}))
    assert response.status_code == 200
    lines = [line.split('\t')
             for line in response.content.decode().split('\r\n')]
    return dict(zip(lines[0], lines[1]))


@pytest.mark.django_db
def test_a_downloaded_revision_has_the_values_of_the_revision(
  client, logged_in, any_added_issue, any_editing_changeset):
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=any_editing_changeset)
    revision.notes = 'Notes of the revision'
    revision.save()

    issue_line = _issue_line(client, revision)

    assert issue_line['number'] == any_added_issue.number
    # names are written in the notation, which keeps their spaces
    assert [item.name.label
            for item in parse_items(issue_line['brand_emblem'])] == [
      any_added_issue.brand_emblem.get().name]
    assert [item.name.label
            for item in parse_items(issue_line['indicia_publisher'])] == [
      any_added_issue.indicia_publisher.name]
    assert issue_line['notes'] == 'Notes of the revision'
    # the on-sale date of the fixture is uncertain
    assert issue_line['on_sale_date'] == '1946-11-23'
    assert issue_line['on_sale_date_uncertain'] == YES


@pytest.mark.django_db
def test_a_downloaded_revision_has_its_own_on_sale_date_certainty(
  client, logged_in, any_added_issue, any_editing_changeset):
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=any_editing_changeset)
    revision.on_sale_date_uncertain = False
    revision.save()

    issue_line = _issue_line(client, revision)
    assert issue_line['on_sale_date'] == '1946-11-23'
    assert issue_line.get('on_sale_date_uncertain', '') == ''


@pytest.mark.django_db
def test_an_issue_being_added_can_be_downloaded(client, logged_in,
                                                any_added_issue_rev):
    assert _issue_line(client, any_added_issue_rev)['number'] == '42'
