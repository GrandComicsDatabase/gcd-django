from datetime import date, timedelta

import pytest

from django.contrib.auth.models import User
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.oi import states

# Days from today to the away date of the editor, None for no date, and
# whether a change still goes to the editor.
AWAY_DAYS = ((None, True), (-1, True), (0, False), (7, False))


def _editor(country, away_days):
    """An editor away until today plus away_days, or with no away date."""
    user = User.objects.create_user(
      'editor', first_name='Some', last_name='Editor',
      email='editor@example.com', password='editor')
    editor = Indexer.objects.create(user=user, country=country)
    if away_days is not None:
        editor.away_until = date.today() + timedelta(days=away_days)
        editor.save()
    return user


def _submit(client, changeset):
    """Submit the change as its author and read it back."""
    author = changeset.indexer
    author.is_superuser = True
    author.save()
    client.force_login(author)
    response = client.post(reverse('submit', kwargs={'id': changeset.id}),
                           {'comments': ''})
    assert response.status_code == 302
    changeset.refresh_from_db()


def _assert_sent(changeset, editor, mailbox, to_editor):
    """The change is with the editor and mailed, or in the general queue."""
    if to_editor:
        assert changeset.state == states.REVIEWING
        assert changeset.approver == editor
        assert [message.to for message in mailbox] == [[editor.email]]
    else:
        assert changeset.state == states.PENDING
        assert changeset.approver is None
        assert mailbox == []


@pytest.mark.django_db
@pytest.mark.parametrize(('away_days', 'to_editor'), AWAY_DAYS)
def test_resubmitted_change_skips_an_editor_who_is_away(
        client, mailoutbox, any_country, any_added_publisher_rev,
        away_days, to_editor):
    editor = _editor(any_country, away_days)
    changeset = any_added_publisher_rev.changeset
    changeset.approver = editor
    changeset.save()

    _submit(client, changeset)

    _assert_sent(changeset, editor, mailoutbox, to_editor)


@pytest.mark.django_db
@pytest.mark.parametrize(('away_days', 'to_editor'), AWAY_DAYS)
def test_change_of_a_new_indexer_skips_a_mentor_who_is_away(
        client, mailoutbox, any_country, any_added_publisher_rev,
        away_days, to_editor):
    mentor = _editor(any_country, away_days)
    changeset = any_added_publisher_rev.changeset
    author = changeset.indexer.indexer
    author.is_new = True
    author.mentor = mentor
    author.save()

    _submit(client, changeset)

    _assert_sent(changeset, mentor, mailoutbox, to_editor)
