"""The sample issues have approved revisions, like issues saved through the
site, so they can be edited."""

import pytest

from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse

from apps.gcd.models import Issue
from apps.oi import states
from apps.oi.models import IssueRevision

SAMPLE_SERIES = '[GCD DEV] Adventures'


@pytest.mark.django_db
@pytest.mark.parametrize('sort_code', [1, 2])
def test_a_sample_issue_can_be_edited(client, sort_code):
    call_command('seed_development_data')
    issue = Issue.objects.get(series__name=SAMPLE_SERIES, sort_code=sort_code)
    client.force_login(User.objects.get(username='editor'))

    response = client.post(reverse('reserve_revision', kwargs={
      'model_name': 'issue', 'id': issue.id}), follow=True)

    changeset = issue.revisions.get(changeset__state=states.OPEN).changeset
    assert response.redirect_chain == [
      (reverse('edit', kwargs={'id': changeset.id}), 302)]
    assert response.status_code == 200
    assert changeset.storyrevisions.count() == issue.active_stories().count()


@pytest.mark.django_db
def test_seeding_again_adds_revisions_only_where_missing():
    call_command('seed_development_data')
    revisions = IssueRevision.objects.count()
    IssueRevision.objects.filter(issue__series__name=SAMPLE_SERIES,
                                 issue__sort_code=2).delete()

    call_command('seed_development_data')

    assert IssueRevision.objects.count() == revisions
