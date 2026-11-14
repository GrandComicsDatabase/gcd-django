import pytest

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.oi.models import IssueRevision


@pytest.mark.django_db
def test_import_error_escapes_file_content(client, any_indexer,
                                           any_added_series):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    upload = SimpleUploadedFile('issues.csv',
                                b'<img src=x onerror=alert(1)>\n')

    response = client.post(
      reverse('import_issues_to_series',
              kwargs={'series_id': any_added_series.id}),
      {'file': upload}, follow=True)

    content = response.content.decode()
    assert '&lt;img src=x onerror=alert(1)&gt;' in content
    assert '<img src=x onerror' not in content
    assert 'Back to the <a href="' in content


@pytest.mark.django_db
@pytest.mark.parametrize('has_indicia_printer', (False, True))
def test_import_adds_issues_with_or_without_printers(
  client, any_indexer, any_added_series, has_indicia_printer):
    any_added_series.has_indicia_printer = has_indicia_printer
    any_added_series.save()
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    upload = SimpleUploadedFile(
      'issues.csv', b'1,,,,January 2000,2000-01-00,,1.00 USD,32,None\n')

    response = client.post(
      reverse('import_issues_to_series',
              kwargs={'series_id': any_added_series.id}),
      {'file': upload})

    assert response.status_code == 302
    assert response.url == reverse('editing')
    assert IssueRevision.objects.get(series=any_added_series).number == '1'
