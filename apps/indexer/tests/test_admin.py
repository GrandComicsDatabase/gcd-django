import re

import pytest
from django.contrib.auth.models import Group, Permission, User

from apps.indexer.models import Indexer
from apps.stddata.models import Country, Language

pytestmark = pytest.mark.django_db

ADD_URL = '/admin/indexer/indexer/add/'
CHANGE_URL = '/admin/indexer/indexer/%d/change/'


@pytest.fixture
def editor():
    group = Group.objects.create(name='editor')
    group.permissions.add(Permission.objects.get(codename='can_mentor'))
    user = User.objects.create_user('an_editor')
    user.groups.add(group)
    return user


@pytest.fixture
def former_editor():
    return User.objects.create_user('former_editor')


@pytest.fixture
def indexer():
    """
    An indexer whose own user, like the admin user, is not an editor.
    """
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    return Indexer.objects.create(user=User.objects.create_user('an_indexer'),
                                  country=country)


def _mentor_options(response):
    """
    The ids of the users offered in the Mentor list of the rendered page.
    """
    select = re.search(r'<select name="mentor".*?</select>',
                       response.content.decode(), re.DOTALL).group()
    return {int(pk) for pk in re.findall(r'<option value="(\d+)"', select)}


def _save(admin_client, indexer, mentor):
    language = Language.objects.get_or_create(code='xzz',
                                              name='Test Language')[0]
    return admin_client.post(
      CHANGE_URL % indexer.id,
      {'user': indexer.user_id, 'country': indexer.country_id,
       'languages': [language.id], 'max_reservations': 1, 'max_ongoing': 0,
       'mentor': mentor.id, '_save': 'Save'})


def test_change_page_offers_only_editors_as_mentor(admin_client, editor,
                                                   indexer):
    response = admin_client.get(CHANGE_URL % indexer.id)

    assert response.status_code == 200
    assert _mentor_options(response) == {editor.id}


def test_add_page_offers_only_editors_as_mentor(admin_client, editor, indexer):
    response = admin_client.get(ADD_URL)

    assert response.status_code == 200
    assert _mentor_options(response) == {editor.id}


def test_current_mentor_is_kept_if_no_longer_an_editor(admin_client, editor,
                                                       former_editor, indexer):
    indexer.mentor = former_editor
    indexer.save()

    response = admin_client.get(CHANGE_URL % indexer.id)

    assert _mentor_options(response) == {editor.id, former_editor.id}


def test_indexer_keeping_a_former_editor_as_mentor_can_be_saved(
      admin_client, former_editor, indexer):
    indexer.mentor = former_editor
    indexer.save()

    response = _save(admin_client, indexer, former_editor)

    assert response.status_code == 302
    indexer.refresh_from_db()
    assert indexer.mentor == former_editor


def test_user_who_is_not_an_editor_cannot_be_set_as_mentor(
      admin_client, editor, former_editor, indexer):
    response = _save(admin_client, indexer, former_editor)

    assert response.status_code == 200
    assert 'mentor' in response.context['adminform'].form.errors
    indexer.refresh_from_db()
    assert indexer.mentor is None


def test_editor_can_be_set_as_mentor(admin_client, editor, indexer):
    response = _save(admin_client, indexer, editor)

    assert response.status_code == 302
    indexer.refresh_from_db()
    assert indexer.mentor == editor


def test_page_opens_for_staff_who_can_only_view_it(client, indexer):
    staff = User.objects.create_user('view_only', is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename='view_indexer'))
    client.force_login(staff)

    response = client.get(CHANGE_URL % indexer.id)

    assert response.status_code == 200
    assert b'<select name="mentor"' not in response.content
