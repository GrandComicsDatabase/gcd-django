"""Tests for the links that report a wrong record to the Error Tracker."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.gcd.models import Issue


@pytest.mark.django_db
def test_error_tracker_links_carry_the_whole_address(client):
    """
    "Report Information" and the "let us know" link of the footer give
    the Error Tracker the whole address of the page, its query included.
    """
    call_command('seed_development_data')
    issue = Issue.objects.filter(variant_of=None, deleted=False).first()
    path = reverse('show_issue', kwargs={'issue_id': issue.id})
    response = client.get(path + '?a=1&b=2')
    content = response.content.decode()

    assert response.status_code == 200
    address = 'bug_file_loc=http%3A//testserver' + path + '%3Fa%3D1%26b%3D2'
    assert content.count(address + '&amp;short_desc=') == 2
