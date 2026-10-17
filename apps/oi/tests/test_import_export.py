import pytest

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


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
