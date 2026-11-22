# -*- coding: utf-8 -*-
"""Tests of what the download page says about the three dump files."""

import pytest
from django.contrib.auth.models import User
from django.template.defaultfilters import filesizeformat
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.stddata.models import Country

# The content of each dump file, by the setting that names it; each file
# has its own size.
DUMPS = {'MYSQL_DUMP': b'm' * 3000,
         'NAME_VALUE_DUMP': b'n' * 20000,
         'SQLITE_DUMP': b's' * 500}


@pytest.fixture
def member(db):
    """A user with an indexer profile."""
    country = Country.objects.get_or_create(
        code='XZY', defaults={'name': 'Test Country'})[0]
    user = User.objects.create_user('a_member', email='member@example.com')
    Indexer.objects.create(user=user, country=country)
    return user


@pytest.fixture
def media(settings, tmp_path):
    """An empty media folder with the folder of the dumps."""
    settings.MEDIA_ROOT = str(tmp_path)
    folder = tmp_path / settings.DUMP_DIR
    folder.mkdir()
    return folder


@pytest.fixture
def dumps(settings, media):
    """The three dump files."""
    for setting, content in DUMPS.items():
        (media / getattr(settings, setting)).write_bytes(content)


def _page(client, member):
    """The download page as the member sees it."""
    client.force_login(member)
    response = client.get(reverse('stats:download'))
    assert response.status_code == 200
    return response


def test_page_names_the_three_files_with_their_sizes(client, member, dumps):
    """The text names the three files; each has its date and its size."""
    response = _page(client, member)
    page = response.content.decode()

    assert 'only available as a MySQL dump' not in page
    assert 'a MySQL dump, a Name-Value dump and an' in page
    assert [(name, size) for name, _date, size
            in response.context['dumps']] == [
        ('MySQL', 3000), ('Name-Value', 20000), ('SQLite', 500)]
    for content in DUMPS.values():
        assert '(%s)' % filesizeformat(len(content)) in page


def test_page_gives_no_size_for_a_missing_file(client, member, media):
    """A file that is not there is dated "never" and has no size."""
    response = _page(client, member)

    assert [row[1:] for row in response.context['dumps']] == [
        ('never', None)] * 3


def test_license_links_name_the_license_in_force(client, member, media):
    """No link text names the 3.0 license that 4.0 replaced."""
    page = _page(client, member).content.decode()

    assert 'Creative Commons 3.0' not in page
    assert 'Upgrade Data License to CC BY-SA 4.0' in page


@pytest.mark.parametrize('button, setting', [
    ('mysqldump', 'MYSQL_DUMP'),
    ('name-value', 'NAME_VALUE_DUMP'),
    ('sqlite', 'SQLITE_DUMP')])
def test_each_button_sends_its_file_as_current_zip(client, member, dumps,
                                                   button, setting):
    """Each button sends its own file, saved under the name current.zip."""
    client.force_login(member)
    response = client.post(reverse('stats:download'),
                           {'accept_license': 'on', button: 'Download'})

    assert response['Content-Disposition'] == \
        'attachment; filename=current.zip'
    assert b''.join(response.streaming_content) == DUMPS[setting]
    response.close()
