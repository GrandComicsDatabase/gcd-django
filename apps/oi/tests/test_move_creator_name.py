# -*- coding: utf-8 -*-
"""Tests of giving a creator name to another creator, through the views."""

import re
from unittest.mock import patch

import pytest

from django.contrib.auth.models import Permission, User
from django.urls import reverse

from apps.gcd.models import (Creator, CreatorRelation, CreatorSignature,
                             CreditType, IssueCredit, NameType, RelationType,
                             StoryCredit)
from apps.gcd.models.creator import NAME_TYPES
from apps.indexer.models import Indexer
from apps.oi import states
from apps.oi.forms.creator import CreatorNameDetailRevisionForm
from apps.oi.models import (Changeset, CreatorNameDetailRevision,
                            CreatorRevision, CTYPES, StoryCreditRevision,
                            _get_revision_lock)
from apps.oi.templatetags.editing import is_locked
from apps.stddata.models import Date, Script


def _script():
    """Return the script that names are in by default."""
    script, _ = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    return script


def _open_changes():
    """Say whether any change is still waiting, besides the approved ones."""
    return Changeset.objects.exclude(state=states.APPROVED).exists()


def _approved_change(indexer):
    """Return a changeset for revisions that are already approved."""
    return Changeset.objects.create(indexer=indexer, state=states.APPROVED,
                                    change_type=CTYPES['creator'])


def _commit_name(changeset, creator_revision, **values):
    """Add a name to the creator of the revision through an approved one."""
    revision = CreatorNameDetailRevision.objects.create(
      changeset=changeset, creator_revision=creator_revision,
      in_script=_script(), sort_name=values['name'], **values)
    revision.commit_to_display()
    return revision.creator_name_detail


def _creator(name, indexer):
    """Create a creator with its official name through approved revisions."""
    changeset = _approved_change(indexer)
    revision = CreatorRevision.objects.create(
      changeset=changeset, gcd_official_name=name,
      birth_date=Date.objects.create(), death_date=Date.objects.create())
    CreatorNameDetailRevision.objects.create(
      changeset=changeset, creator_revision=revision, name=name,
      sort_name=name, is_official_name=True, in_script=_script())
    revision.commit_to_display()
    changeset.creatornamedetailrevisions.get().commit_to_display()
    return revision.creator


def _other_name(creator, name='J. Smith', type_id=None):
    """Add a name that is not the official one to the creator."""
    name_type = None
    if type_id:
        name_type, _ = NameType.objects.get_or_create(
          id=type_id, defaults={'type': 'type %d' % type_id})
    creator_revision = creator.revisions.latest('id')
    return _commit_name(_approved_change(creator_revision.changeset.indexer),
                        creator_revision, name=name, type=name_type)


def _editor(username, country):
    """Create a user who may reserve and approve."""
    user = User.objects.create_user(username, password=username)
    Indexer.objects.create(user=user, country=country)
    user.user_permissions.add(*Permission.objects.filter(
      codename__in=['can_reserve', 'can_approve'],
      content_type__app_label='indexer'))
    return user


def _url(name):
    """Return the address of the page that moves the name."""
    return reverse('move_creator_name', kwargs={'creator_name_id': name.id})


def _credit_type():
    """Return the credit type used by the credits of these tests."""
    return CreditType.objects.get_or_create(
      name='script', defaults={'sort_code': 1})[0]


def _relation(from_creator, to_creator, name):
    """Create a relation between two creators that uses the name."""
    relation = CreatorRelation.objects.create(
      from_creator=from_creator, to_creator=to_creator,
      relation_type=RelationType.objects.create(type='alias',
                                                reverse_type='alias of'))
    relation.creator_name.add(name)
    return relation


def _approve(client, changeset, country):
    """Assign the changeset to a second editor, who approves it."""
    client.force_login(_editor('approver', country))
    for action in ('assign', 'approve'):
        response = client.post(
          reverse('process', kwargs={'id': changeset.id}),
          {action: action.title(), 'comments': ''})
        assert response.status_code == 302
    changeset.refresh_from_db()
    assert changeset.state == states.APPROVED


@pytest.fixture
def creators(any_indexer):
    """The creator who has the name, and the one who should have it."""
    return (_creator('Wrong Creator', any_indexer),
            _creator('Right Creator', any_indexer))


@pytest.fixture
def editor(client, any_country):
    """Log in an editor."""
    user = _editor('mover', any_country)
    client.force_login(user)
    return user


def _submit_move(client, name, new_creator, comments=''):
    """Move the name and return the changeset now in the queue."""
    response = client.post(_url(name), {'creator': new_creator.id,
                                        'comments': comments})
    assert response.status_code == 302
    assert response['Location'] == reverse('editing')
    return Changeset.objects.get(
      creatornamedetailrevisions__creator_name_detail=name,
      state=states.PENDING)


@pytest.mark.django_db
def test_the_name_and_its_credits_move_on_approval(
        client, creators, editor, any_added_story, any_country):
    """The name and its credits reach the new creator only on approval."""
    wrong, right = creators
    name = _other_name(wrong)
    credit = StoryCredit.objects.create(
      story=any_added_story, creator=name, credit_type=_credit_type())

    changeset = _submit_move(client, name, right)

    assert changeset.change_type == CTYPES['creator']
    changeset.calculate_imps()
    assert changeset.imps == 0
    comment = changeset.comments.latest('created').text
    assert comment == ('"J. Smith" moves from Wrong Creator to Right Creator,'
                       ' 1 credit(s) follow the name.')
    name.refresh_from_db()
    assert name.creator == wrong

    _approve(client, changeset, any_country)

    name.refresh_from_db()
    credit.refresh_from_db()
    assert name.creator == right
    assert credit.creator.creator == right
    assert name in right.active_names()
    assert name not in wrong.active_names()
    assert wrong.official_creator_detail.name == 'Wrong Creator'
    assert right.official_creator_detail.name == 'Right Creator'


@pytest.mark.django_db
def test_a_move_can_be_undone_with_the_same_steps(client, creators, editor,
                                                  any_country):
    """A second move in the opposite direction brings the name back."""
    wrong, right = creators
    name = _other_name(wrong)
    _approve(client, _submit_move(client, name, right), any_country)

    client.force_login(editor)
    changeset = _submit_move(client, name, wrong)
    client.force_login(User.objects.get(username='approver'))
    for action in ('assign', 'approve'):
        client.post(reverse('process', kwargs={'id': changeset.id}),
                    {action: action.title(), 'comments': ''})

    name.refresh_from_db()
    assert name.creator == wrong


@pytest.mark.django_db
def test_the_compare_page_shows_the_move(client, creators, editor):
    """The approver sees a row with both creators on the compare page."""
    wrong, right = creators
    changeset = _submit_move(client, _other_name(wrong), right)
    right.disambiguation = 'inker'
    right.save()

    html = client.get(reverse('compare',
                              kwargs={'id': changeset.id})).content.decode()

    row = re.search(r'>\s*Creator\s*</td>(.*?)</tr>', html, re.S).group(1)
    assert 'Wrong Creator' in row
    assert 'Right Creator [inker]' in row
    assert right.get_absolute_url() in row
    assert 'moves from Wrong Creator to Right Creator' in html


@pytest.mark.django_db
def test_the_comment_of_the_editor_is_kept(client, creators, editor):
    """The comment of the form is added to the automatic note."""
    wrong, right = creators
    changeset = _submit_move(client, _other_name(wrong), right,
                             'See the signature.')

    assert changeset.comments.latest('created').text.endswith(
      '\nSee the signature.')


@pytest.mark.django_db
def test_the_note_tells_namesakes_apart(client, creators, editor):
    """The automatic note gives the disambiguation of both creators."""
    wrong, right = creators
    for creator, disambiguation in ((wrong, 'inker'), (right, 'penciller')):
        creator.disambiguation = disambiguation
        creator.save()

    changeset = _submit_move(client, _other_name(wrong), right)

    assert ('from Wrong Creator [inker] to Right Creator [penciller],'
            in changeset.comments.latest('created').text)


@pytest.mark.django_db
def test_an_ordinary_edit_of_a_name_is_not_a_move(client, creators, editor):
    """A name edited together with its creator shows no creator change."""
    wrong, _ = creators
    name = _other_name(wrong)
    changeset = Changeset.objects.create(indexer=editor, state=states.OPEN,
                                         change_type=CTYPES['creator'])
    CreatorRevision.clone(wrong, changeset)._create_dependent_revisions()
    revision = changeset.creatornamedetailrevisions.get(
      creator_name_detail=name)
    revision.compare_changes()

    assert 'creator' not in revision.field_list()
    assert revision.is_changed is False
    assert not CreatorNameDetailRevisionForm(
      instance=revision).fields['is_official_name'].disabled


@pytest.mark.django_db
def test_a_later_edit_of_the_new_creator_shows_no_move(client, creators,
                                                       editor, any_country):
    """Once moved, the name is an ordinary name of the new creator."""
    wrong, right = creators
    name = _other_name(wrong)
    _approve(client, _submit_move(client, name, right), any_country)
    changeset = Changeset.objects.create(indexer=editor, state=states.OPEN,
                                         change_type=CTYPES['creator'])
    CreatorRevision.clone(right, changeset)._create_dependent_revisions()
    revision = changeset.creatornamedetailrevisions.get(
      creator_name_detail=name)
    revision.compare_changes()

    assert 'creator' not in revision.field_list()
    assert revision.is_changed is False


@pytest.mark.django_db
def test_a_retracted_move_cannot_make_the_name_official(client, creators,
                                                        editor):
    """The form of a move in progress ignores the official flag and type."""
    wrong, right = creators
    name = _other_name(wrong)
    changeset = _submit_move(client, name, right)
    revision = changeset.creatornamedetailrevisions.get(
      creator_name_detail=name)

    form = CreatorNameDetailRevisionForm(
      {'name': name.name, 'sort_name': name.sort_name,
       'is_official_name': 'on', 'in_script': _script().id},
      instance=revision)

    assert form.is_valid(), form.errors
    assert form.cleaned_data['is_official_name'] is False
    assert form.fields['type'].disabled


@pytest.mark.django_db
def test_approval_marks_the_new_creator_as_changed(client, creators, editor,
                                                   any_country):
    """The search entry of the new creator is rebuilt from its names."""
    wrong, right = creators
    changeset = _submit_move(client, _other_name(wrong), right)
    Creator.objects.filter(id=right.id).update(modified='2000-01-01 00:00:00')

    _approve(client, changeset, any_country)

    right.refresh_from_db()
    assert right.modified.year > 2000


@pytest.mark.django_db
def test_the_history_of_the_old_creator_lists_the_move(client, creators,
                                                       editor, any_country):
    """The approved move is in the history of the creator that had the name."""
    wrong, right = creators
    changeset = _submit_move(client, _other_name(wrong), right)
    _approve(client, changeset, any_country)

    html = client.get(reverse(
      'change_history',
      kwargs={'model_name': 'creator', 'id': wrong.id})).content.decode()

    assert reverse('compare', kwargs={'id': changeset.id}) in html


@pytest.mark.django_db
def test_the_list_of_creators_tells_namesakes_apart(client, creators, editor):
    """The disambiguation is part of the label in the autocomplete."""
    _, right = creators
    right.disambiguation = 'inker'
    right.save()

    results = client.get(reverse('creator_autocomplete'),
                         {'q': 'Right'}).json()['results']

    assert [result['text'] for result in results] == ['Right Creator [inker]']


@pytest.mark.django_db
def test_the_page_counts_story_and_issue_credits(client, creators, editor,
                                                 any_added_story):
    """Credits of sequences and of issues both follow the name."""
    name = _other_name(creators[0])
    StoryCredit.objects.create(story=any_added_story, creator=name,
                               credit_type=_credit_type())
    IssueCredit.objects.create(issue=any_added_story.issue, creator=name,
                               credit_type=_credit_type())

    html = client.get(_url(name)).content.decode()

    assert '2 credits using this name' in html


@pytest.mark.django_db
def test_the_page_says_how_many_credits_follow(client, creators, editor):
    """The form page states the number of credits that follow the name."""
    name = _other_name(creators[0])

    response = client.get(_url(name))

    assert response.status_code == 200
    assert '0 credits using this name' in response.content.decode()


@pytest.mark.django_db
def test_only_an_editor_can_move_a_name(client, creators, any_indexer):
    """An indexer without the approve permission is sent to the login."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    name = _other_name(creators[0])

    response = client.post(_url(name), {'creator': creators[1].id})

    assert response.status_code == 302
    assert 'login' in response['Location']
    assert not _open_changes()


@pytest.mark.django_db
def test_the_official_name_cannot_move(client, creators, editor):
    """The official name stays with its creator."""
    official = creators[0].official_creator_detail

    response = client.post(_url(official), {'creator': creators[1].id})

    assert 'cannot be moved' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
@pytest.mark.parametrize('type_name', ['house', 'studio', 'ghost', 'joint'])
def test_a_name_of_a_relation_type_cannot_move(client, creators, editor,
                                               type_name):
    """House, studio, ghost and joint names are refused."""
    name = _other_name(creators[0], type_id=NAME_TYPES[type_name])

    response = client.post(_url(name), {'creator': creators[1].id})

    assert 'cannot be moved' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
def test_a_name_used_by_a_relation_cannot_move(client, creators, editor):
    """A name attached to a creator relation is refused."""
    wrong, right = creators
    name = _other_name(wrong)
    _relation(wrong, right, name)

    response = client.post(_url(name), {'creator': right.id})

    assert 'cannot be moved' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
def test_a_deleted_relation_does_not_stop_a_move(client, creators, editor):
    """Only a relation still in place keeps the name where it is."""
    wrong, right = creators
    name = _other_name(wrong)
    relation = _relation(wrong, right, name)
    relation.deleted = True
    relation.save()

    assert client.get(_url(name)).status_code == 200
    assert _submit_move(client, name, right).state == states.PENDING


@pytest.mark.django_db
def test_a_name_with_a_signed_credit_cannot_move(client, creators, editor,
                                                 any_added_story):
    """The signature on a credit belongs to the present creator."""
    wrong, right = creators
    name = _other_name(wrong)
    StoryCredit.objects.create(
      story=any_added_story, creator=name, credit_type=_credit_type(),
      signature=CreatorSignature.objects.create(creator=wrong, name='Scrawl'))

    response = client.post(_url(name), {'creator': right.id})

    assert 'cannot be moved' in response.content.decode()
    assert not Changeset.objects.filter(indexer=editor).exists()


@pytest.mark.django_db
def test_a_name_with_a_pending_signed_credit_cannot_move(client, creators,
                                                         editor,
                                                         any_added_story_rev):
    """A signature waiting in the queue blocks the move as well."""
    wrong, right = creators
    name = _other_name(wrong)
    changeset = any_added_story_rev.changeset
    changeset.state = states.PENDING
    changeset.save()
    StoryCreditRevision.objects.create(
      changeset=changeset, story_revision=any_added_story_rev, creator=name,
      credit_type=_credit_type(),
      signature=CreatorSignature.objects.create(creator=wrong, name='Scrawl'))

    response = client.post(_url(name), {'creator': right.id})

    assert 'cannot be moved' in response.content.decode()
    assert not Changeset.objects.filter(indexer=editor).exists()


@pytest.mark.django_db
def test_the_refusal_page_escapes_the_name(client, creators, editor):
    """A name is shown as text on the page of the refusal."""
    name = _other_name(creators[0], '<b>House</b>', NAME_TYPES['house'])

    html = client.get(_url(name)).content.decode()

    assert '&lt;b&gt;House' in html
    assert '<b>House' not in html


@pytest.mark.django_db
def test_a_deleted_name_is_not_found(client, creators, editor):
    """The page of a deleted name does not exist."""
    name = _other_name(creators[0])
    name.deleted = True
    name.save()

    assert client.get(_url(name)).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize('same_name', ['J. Smith', 'J. Sm' + chr(0xed) + 'th'])
def test_a_name_the_new_creator_already_has_is_refused(client, creators,
                                                       editor, same_name):
    """The new creator would have the same name twice."""
    wrong, right = creators
    name = _other_name(wrong)
    _other_name(right, same_name)

    response = client.post(_url(name), {'creator': right.id})

    assert 'already has this name' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
def test_a_name_reserved_on_its_own_stops_the_move(client, creators, editor,
                                                   any_indexer):
    """A failed reservation deletes its change and frees the creator."""
    wrong, right = creators
    name = _other_name(wrong)
    other = Changeset.objects.create(indexer=any_indexer, state=states.OPEN,
                                     change_type=CTYPES['creator'])
    assert _get_revision_lock(name, changeset=other)

    # The models that only the tests define have no table to delete from.
    with patch.object(Changeset, 'delete') as delete:
        response = client.post(_url(name), {'creator': right.id})

    assert 'is reserved' in response.content.decode()
    assert not is_locked(wrong)
    delete.assert_called_once()


@pytest.mark.django_db
def test_an_editor_at_the_reservation_limit_is_refused(client, creators,
                                                       editor):
    """An editor who cannot reserve another change gets a message."""
    Indexer.objects.filter(user=editor).update(max_reservations=0)
    name = _other_name(creators[0])

    response = client.post(_url(name), {'creator': creators[1].id})

    assert 'cannot reserve another change' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
def test_a_name_cannot_move_to_its_own_creator(client, creators, editor):
    """The form refuses the creator that already has the name."""
    name = _other_name(creators[0])

    response = client.post(_url(name), {'creator': creators[0].id})

    assert 'already belongs to this creator' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
def test_a_name_cannot_move_to_a_deleted_creator(client, creators, editor):
    """A deleted creator is not a valid choice."""
    wrong, right = creators
    name = _other_name(wrong)
    right.deleted = True
    right.save()

    response = client.post(_url(name), {'creator': right.id})

    assert response.status_code == 200
    assert 'Select a valid choice' in response.content.decode()
    assert not _open_changes()


@pytest.mark.django_db
def test_a_name_cannot_move_to_a_creator_being_deleted(client, creators,
                                                       editor):
    """A creator with a pending deletion is refused."""
    wrong, right = creators
    name = _other_name(wrong)
    changeset = Changeset.objects.create(indexer=editor, state=states.PENDING,
                                         change_type=CTYPES['creator'])
    revision = CreatorRevision.clone(right, changeset)
    revision.deleted = True
    revision.save()

    response = client.post(_url(name), {'creator': right.id})

    assert 'has a pending deletion' in response.content.decode()
    assert not Changeset.objects.filter(
      creatornamedetailrevisions__creator_name_detail=name,
      state__in=states.ACTIVE).exists()


@pytest.mark.django_db
def test_a_reserved_creator_is_refused(client, creators, editor, any_indexer):
    """A creator reserved by someone else stops the move."""
    wrong, right = creators
    name = _other_name(wrong)
    other = Changeset.objects.create(indexer=any_indexer, state=states.OPEN,
                                     change_type=CTYPES['creator'])
    assert _get_revision_lock(wrong, changeset=other)

    response = client.post(_url(name), {'creator': right.id})

    assert 'is reserved' in response.content.decode()
    name.refresh_from_db()
    assert name.creator == wrong


@pytest.mark.django_db
def test_cancel_goes_back_to_the_creator(client, creators, editor):
    """Cancel returns to the creator page and reserves nothing."""
    name = _other_name(creators[0])

    html = client.get(_url(name)).content.decode()
    assert re.search(r'name="cancel"\s+formnovalidate', html)

    response = client.post(_url(name), {'cancel': 'Cancel'})

    assert response.status_code == 302
    assert response['Location'] == creators[0].get_absolute_url()
    assert not _open_changes()


@pytest.mark.django_db
def test_the_target_cannot_be_deleted_while_the_move_is_pending(
        client, creators, editor):
    """A pending move blocks the deletion of the new creator."""
    wrong, right = creators
    _submit_move(client, _other_name(wrong), right)

    assert right.deletable() is False


@pytest.mark.django_db
def test_discarding_the_move_leaves_the_name_where_it_was(client, creators,
                                                          editor, any_country):
    """A discarded move frees the locks and changes nothing."""
    wrong, right = creators
    name = _other_name(wrong)
    changeset = _submit_move(client, name, right)

    changeset.discard(editor)

    changeset.refresh_from_db()
    assert changeset.state == states.DISCARDED
    name.refresh_from_db()
    assert name.creator == wrong
    assert not is_locked(wrong)
    assert not is_locked(name)


@pytest.mark.django_db
def test_the_creator_page_links_the_move_for_editors_only(client, creators,
                                                          any_indexer, editor):
    """The link appears for editors, only on names that can move."""
    wrong, right = creators
    name = _other_name(wrong)
    house = _other_name(wrong, 'House Name', NAME_TYPES['house'])

    html = client.get(wrong.get_absolute_url()).content.decode()

    assert _url(name) in html
    assert _url(house) not in html
    assert _url(wrong.official_creator_detail) not in html

    client.force_login(any_indexer)
    assert _url(name) not in client.get(
      wrong.get_absolute_url()).content.decode()
