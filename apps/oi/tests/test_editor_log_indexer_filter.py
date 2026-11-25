import pytest

from django.contrib.auth.models import Permission, User
from django.http import QueryDict
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.oi import states, views
from apps.oi.models import (Changeset, ChangesetComment, PublisherRevision,
                            CTYPES)


def _user(username, first_name, last_name, country, **indexer_values):
    user = User.objects.create_user(username, first_name=first_name,
                                    last_name=last_name, password=username)
    Indexer.objects.create(user=user, country=country, **indexer_values)
    return user


def _reviewed(editor, indexer, country):
    """A change of the indexer that the editor approved."""
    changeset = Changeset.objects.create(
      state=states.APPROVED, indexer=indexer, approver=editor,
      change_type=CTYPES['publisher'])
    PublisherRevision.objects.create(changeset=changeset,
                                     name='Test Publisher', country=country)
    ChangesetComment.objects.create(
      changeset=changeset, commenter=editor, text='',
      old_state=states.REVIEWING, new_state=states.APPROVED)
    return changeset


@pytest.fixture
def editor(any_country):
    editor = _user('editor', 'Some', 'Editor', any_country)
    editor.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    return editor


@pytest.fixture
def changes(editor, any_country):
    """
    The changes the editor reviewed: of a current mentee, of a former
    mentee and of another indexer.
    """
    indexers = {
      'mentee': _user('mentee', 'Some', 'Mentee', any_country,
                      mentor=editor, is_new=True),
      'former': _user('former', 'Former', 'Mentee', any_country,
                      mentor=editor),
      'other': _user('other', 'Some', 'Indexer', any_country),
    }
    return {name: _reviewed(editor, indexer, any_country)
            for name, indexer in indexers.items()}


@pytest.mark.django_db
def test_editor_log_shows_only_the_chosen_indexer(client, editor, changes):
    client.force_login(editor)
    response = client.get(reverse('editor_log'),
                          {'indexer': changes['other'].indexer_id})

    assert list(response.context['items']) == [changes['other']]


@pytest.mark.django_db
def test_indexer_choices_list_current_mentees_first(client, editor, changes,
                                                    any_country):
    other_editor = _user('other_editor', 'Other', 'Editor', any_country)
    _reviewed(other_editor,
              _user('stranger', 'Other', 'Indexer', any_country),
              any_country)
    client.force_login(editor)
    response = client.get(reverse('editor_log'))

    field = response.context['filter_form'].fields['indexer']
    assert list(field.choices) == [
      ('', 'All indexers'),
      ('Your mentees', [(changes['mentee'].indexer_id, 'Some Mentee')]),
      ('Other indexers', [(changes['other'].indexer_id, 'Some Indexer'),
                          (changes['former'].indexer_id, 'Former Mentee')]),
    ]


@pytest.mark.django_db
def test_indexer_choices_take_one_query(editor, changes,
                                        django_assert_num_queries):
    reviewed = Changeset.objects.filter(approver=editor)

    with django_assert_num_queries(1):
        log_filter = views.EditorLogFilter(QueryDict(), reviewed,
                                           editor=editor)
        choices = list(log_filter.form.fields['indexer'].choices)

    assert len(choices) == 3
