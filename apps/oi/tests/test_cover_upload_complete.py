"""
The page after a cover upload offers to edit the issue when the issue has
no publication date and is not reserved by a change.  The button reserves
the issue as the Edit button of the issue page does, so the date goes
through the usual issue edit.
"""
import io
import os
import re

import pytest
from PIL import Image as pyImage

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.gcd.models import Issue
from apps.oi import states
from apps.oi.models import Changeset, CoverRevision, CTYPES, \
                           IssueRevision, RevisionLock

BUTTON = 'Add the Publication Date'


@pytest.fixture
def media_root(tmp_path):
    """Store the uploaded scans in a temporary media folder."""
    os.makedirs(tmp_path / 'img' / 'gcd' / 'new_covers' / 'tmp')
    with override_settings(MEDIA_ROOT=f'{tmp_path}/'):
        yield tmp_path


@pytest.fixture
def issue_without_date(any_added_issue):
    """The sample issue with its publication date left empty."""
    Issue.objects.filter(id=any_added_issue.id).update(publication_date='')
    return Issue.objects.get(id=any_added_issue.id)


def _reserve_url(issue):
    """The address the Edit button of the issue page posts to."""
    return reverse('reserve_revision',
                   kwargs={'model_name': 'issue', 'id': issue.id})


def _upload(client, issue):
    """Upload a cover for issue and return the page shown after it."""
    scan = io.BytesIO()
    pyImage.new('RGB', (400, 600), 'white').save(scan, 'JPEG')
    return client.post(
      reverse('upload_cover', kwargs={'issue_id': issue.id}),
      {'scan': SimpleUploadedFile('cover.jpg', scan.getvalue()),
       'source': 'scanned myself', 'comments': ''}, follow=True)


def _complete_page(client, issue, indexer):
    """The page after the upload of a pending cover of issue."""
    changeset = Changeset.objects.create(
      indexer=indexer, state=states.PENDING, change_type=CTYPES['cover'])
    revision = CoverRevision.objects.create(changeset=changeset, issue=issue)
    return client.get(reverse('upload_cover_complete',
                              kwargs={'revision_id': revision.id}))


@pytest.mark.django_db
def test_upload_offers_to_add_the_date(client, any_indexer,
                                       issue_without_date, media_root):
    """The upload leaves the issue free, so the page has the button."""
    client.force_login(any_indexer)

    response = _upload(client, issue_without_date)

    assert response.redirect_chain[-1][0] == reverse(
      'upload_cover_complete',
      kwargs={'revision_id': CoverRevision.objects.get().id})
    html = response.content.decode()
    assert 'action="%s"' % _reserve_url(issue_without_date) in html
    assert BUTTON in html


@pytest.mark.django_db
def test_issue_with_date_has_no_button(client, any_indexer,
                                       any_added_issue):
    """An issue with a publication date gets no button."""
    client.force_login(any_indexer)

    response = _complete_page(client, any_added_issue, any_indexer)

    assert response.status_code == 200
    html = response.content.decode()
    assert _reserve_url(any_added_issue) not in html
    assert BUTTON not in html


@pytest.mark.django_db
def test_reserved_issue_has_no_button(client, any_indexer,
                                      issue_without_date):
    """An issue reserved by a change gets no button."""
    editing = Changeset.objects.create(
      indexer=any_indexer, state=states.OPEN, change_type=CTYPES['issue'])
    RevisionLock.objects.create(locked_object=issue_without_date,
                                changeset=editing)
    client.force_login(any_indexer)

    response = _complete_page(client, issue_without_date, any_indexer)

    assert response.status_code == 200
    html = response.content.decode()
    assert _reserve_url(issue_without_date) not in html
    assert BUTTON not in html


@pytest.mark.django_db
def test_button_opens_the_issue_edit(client, any_indexer,
                                     issue_without_date):
    """The button reserves the issue and opens the change of the issue."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    html = _complete_page(client, issue_without_date,
                          any_indexer).content.decode()
    form = re.search(r'<form method="POST"\s+action="([^"]+)">'
                     r'(?:(?!</form>).)*' + BUTTON, html, re.S)
    assert form, 'no form with the button on the page'

    response = client.post(form.group(1))

    revision = IssueRevision.objects.get(issue=issue_without_date,
                                         changeset__state=states.OPEN)
    assert revision.changeset.indexer == any_indexer
    assert response.status_code == 302
    assert response.url == reverse('edit',
                                   kwargs={'id': revision.changeset.id})
    assert client.get(response.url).status_code == 200
