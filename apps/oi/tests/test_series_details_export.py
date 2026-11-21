"""The download of the issue table of a series has only its shown columns."""
import csv
import io

import pytest

from django.urls import reverse


@pytest.mark.django_db
def test_issue_table_download_has_only_the_shown_columns(client,
                                                         any_added_issue):
    url = reverse('series_details',
                  kwargs={'series_id': any_added_issue.series_id})
    page = client.get(url)
    shown = [str(column.header) for column in page.context['table'].columns]
    download = client.get(url, {'_export': 'csv'})
    header = next(csv.reader(io.StringIO(download.content.decode())))

    assert page.status_code == download.status_code == 200
    # the issue has no volume, title, ISBN, barcode or age guidelines
    assert 'ISBN' not in shown
    assert header == shown
