# -*- coding: utf-8 -*-
"""
Editors choose which cover of an issue with two or more covers of its own
is shown first, from the page that edits the covers of the issue.
"""
from datetime import datetime, timezone

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse

from apps.gcd.models import Cover
from apps.indexer.models import Indexer

OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _user(name, country, editor):
    """A logged-in user with an indexer profile, an editor if asked."""
    user = User.objects.create_user(name, password=name)
    Indexer.objects.create(user=user, country=country)
    if editor:
        user.user_permissions.add(Permission.objects.get(
          codename='can_approve', content_type__app_label='indexer'))
    return user


def _two_covers(issue):
    """Two covers of the issue, as uploaded, with an old modified time."""
    covers = [Cover.objects.create(issue=issue) for i in range(2)]
    Cover.objects.filter(issue=issue).update(modified=OLD)
    return covers


def _show_first(client, user, issue, cover_id):
    """Press "Show first" on the edit covers page of the issue."""
    client.force_login(user)
    return client.post(reverse('edit_covers', kwargs={'issue_id': issue.id}),
                       {'first': cover_id})


def _order(issue):
    """The ids of the covers of the issue, in the order they are shown."""
    return [cover.id for cover in issue.active_covers()]


@pytest.mark.django_db
def test_editor_shows_the_second_cover_first(client, any_added_issue,
                                             any_country):
    first, second = _two_covers(any_added_issue)
    editor = _user('editor', any_country, editor=True)

    response = _show_first(client, editor, any_added_issue, second.id)

    assert response.status_code == 302
    assert response.url == reverse('edit_covers',
                                   kwargs={'issue_id': any_added_issue.id})
    assert _order(any_added_issue) == [second.id, first.id]
    assert any_added_issue.cover_set.first() == second
    assert list(Cover.objects.filter(issue=any_added_issue)
                             .values_list('modified', flat=True)) == [OLD, OLD]


@pytest.mark.django_db
def test_cover_added_after_the_choice_comes_last(client, any_added_issue,
                                                 any_country):
    first, second = _two_covers(any_added_issue)
    editor = _user('editor', any_country, editor=True)
    _show_first(client, editor, any_added_issue, second.id)

    third = Cover.objects.create(issue=any_added_issue)

    assert _order(any_added_issue) == [second.id, first.id, third.id]
    _show_first(client, editor, any_added_issue, third.id)
    assert _order(any_added_issue) == [third.id, second.id, first.id]


@pytest.mark.django_db
def test_series_gallery_shows_the_chosen_cover_first(client, any_added_issue,
                                                     any_country):
    first, second = _two_covers(any_added_issue)
    editor = _user('editor', any_country, editor=True)
    _show_first(client, editor, any_added_issue, second.id)

    response = client.get(reverse(
      'series_covers', kwargs={'series_id': any_added_issue.series.id}))

    rows = response.context['table'].rows
    assert [row.record.id for row in rows] == [second.id, first.id]


@pytest.mark.django_db
def test_button_only_under_the_covers_after_the_first(client,
                                                      any_added_issue,
                                                      any_country):
    first, second = _two_covers(any_added_issue)
    client.force_login(_user('editor', any_country, editor=True))

    response = client.get(reverse('edit_covers',
                                  kwargs={'issue_id': any_added_issue.id}))

    page = response.content.decode()
    assert page.count('value="Show first"') == 1
    assert 'name="first" value="%d"' % second.id in page
    assert 'name="first" value="%d"' % first.id not in page


@pytest.mark.django_db
def test_user_who_is_not_an_editor_gets_an_error(client, any_added_issue,
                                                 any_country):
    first, second = _two_covers(any_added_issue)
    indexer = _user('indexer2', any_country, editor=False)

    response = _show_first(client, indexer, any_added_issue, second.id)

    assert 'Only editors can choose' in response.content.decode()
    assert _order(any_added_issue) == [first.id, second.id]


@pytest.mark.django_db
def test_cover_of_another_issue_is_not_found(client, any_added_issue,
                                             any_added_variant, any_country):
    first, second = _two_covers(any_added_issue)
    other = Cover.objects.create(issue=any_added_variant)
    editor = _user('editor', any_country, editor=True)

    response = _show_first(client, editor, any_added_issue, other.id)
    not_a_number = _show_first(client, editor, any_added_issue, 'x')

    assert response.status_code == 404
    assert not_a_number.status_code == 404
    assert _order(any_added_issue) == [first.id, second.id]
