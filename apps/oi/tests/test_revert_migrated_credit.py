# -*- coding: utf-8 -*-
"""Tests of undoing the migration of a text credit on the edit form."""

import pytest

from django.contrib.auth.models import Permission
from django.forms import CheckboxInput
from django.http import QueryDict
from django.test import RequestFactory
from django.urls import reverse

from apps.gcd.models import (Creator, CreatorNameDetail, CreatorSignature,
                             CreditType, StoryCredit)
from apps.gcd.models.story import CREDIT_TYPES
from apps.oi.forms import get_revision_form
from apps.oi.models import (CTYPES, IssueCreditRevision, IssueRevision,
                            StoryCreditRevision, StoryRevision)
from apps.stddata.models import Date, Script

SCRIPT = 'Anna Alpha; Some Stranger; Bob Beta'
ANNA = ('Anna Alpha', 'script')
BOB = ('Bob Beta', 'script')
ISSUE_ANNA = ('Anna Alpha', 'editing')
REFUSAL = 'would migrate this credit again'


def _creator(name):
    """Create a creator and return the official name."""
    script, _ = Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    creator = Creator.objects.create(
      gcd_official_name=name, birth_date=Date.objects.create(),
      death_date=Date.objects.create(), birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='')
    return CreatorNameDetail.objects.create(
      name=name, creator=creator, is_official_name=True, in_script=script)


def _refetch(revision):
    """Return a new copy of the revision, without any cached state."""
    return type(revision).objects.get(id=revision.id)


def _migrated_with(revision, **old_text):
    """Give the revision and its approved version the text, then migrate."""
    type(revision).objects.filter(
      id__in=[revision.id, revision.previous_revision_id]).update(**old_text)
    revision = _refetch(revision)
    revision.migrate_credits()
    return _refetch(revision)


def _rows(revision):
    """Return the forms of the credit rows of the revision."""
    formset = revision.extra_forms(RequestFactory().get('/'))[
      'credits_formset']
    return formset.initial_forms


def _key(form):
    """Return the creator name and credit type of a credit row."""
    return (form.instance.creator.name, form.instance.credit_type.name)


def _offered(revision):
    """Return the credit rows which offer to revert the migration."""
    return [_key(form) for form in _rows(revision)
            if 'revert_migration' in form.fields]


def _credits(revision):
    """Return all the credit rows of the revision, by name and type."""
    return [_key(form) for form in _rows(revision)]


def _form_data(form):
    """Return the data a browser sends for a form saved unchanged."""
    data = QueryDict(mutable=True)
    for bound_field in form:
        value = bound_field.value()
        if isinstance(bound_field.field.widget, CheckboxInput):
            if value:
                data[bound_field.html_name] = 'on'
        elif isinstance(value, (list, tuple)):
            data.setlist(bound_field.html_name, [str(v) for v in value])
        elif value is not None:
            data[bound_field.html_name] = str(value)
    return data


def _save(client, user, revision, revert=(), remove=(), button='save',
          **changes):
    """Press a button on the edit page, after changing the given things."""
    revision = _refetch(revision)
    form = get_revision_form(revision, user=user)(instance=revision)
    data = _form_data(form)
    extra_forms = revision.extra_forms(RequestFactory().get('/'))
    for formset in extra_forms.values():
        if formset:
            data.update(_form_data(formset.management_form))
            for row in formset.forms:
                data.update(_form_data(row))
    for row in extra_forms['credits_formset'].initial_forms:
        if _key(row) in revert:
            data[row.add_prefix('revert_migration')] = 'on'
        if _key(row) in remove:
            data[row.add_prefix('DELETE')] = 'on'
    data.update(changes)
    data[button] = 'Save'
    return client.post(reverse('process_revision',
                               kwargs={'id': revision.id,
                                       'model_name': revision.source_name}),
                       data)


@pytest.fixture(autouse=True)
def credit_types(db):
    """The credit types, which migration refers to by their id."""
    for name, type_id in CREDIT_TYPES.items():
        CreditType.objects.get_or_create(
          id=type_id, defaults={'name': name, 'sort_code': type_id})


@pytest.fixture
def names(db):
    """The names of two creators, who are in the text credits."""
    return {name: _creator(name) for name in ('Anna Alpha', 'Bob Beta')}


@pytest.fixture
def indexer(client, any_indexer):
    """Log in the indexer who owns the changes."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    return any_indexer


@pytest.fixture
def issue_change(any_editing_changeset):
    """An open change of the kind that edits an issue and its sequences."""
    any_editing_changeset.change_type = CTYPES['issue']
    any_editing_changeset.save()
    return any_editing_changeset


@pytest.fixture
def migrated(issue_change, any_edit_story_rev, names):
    """An edited sequence whose script has just been migrated."""
    return _migrated_with(any_edit_story_rev, script=SCRIPT)


@pytest.fixture
def migrated_issue(issue_change, any_added_issue, names):
    """An edited issue whose editing has just been migrated."""
    return _migrated_with(IssueRevision.clone(any_added_issue, issue_change),
                          editing='Anna Alpha; Some Stranger')


@pytest.mark.django_db
def test_revert_puts_one_credit_back_in_its_old_place(client, indexer,
                                                      migrated):
    """Only the checked row is reverted, in its place in the old order."""
    assert migrated.script == 'Some Stranger'
    assert _offered(migrated) == [ANNA, BOB]

    response = _save(client, indexer, migrated, revert=[ANNA])

    assert response.status_code == 302
    migrated = _refetch(migrated)
    assert migrated.script == 'Anna Alpha; Some Stranger'
    assert _credits(migrated) == [BOB]


@pytest.mark.django_db
def test_revert_of_the_last_credit_goes_after_the_rest(client, indexer,
                                                       migrated):
    """A credit which came last in the old text is put back at the end."""
    response = _save(client, indexer, migrated, revert=[BOB])

    assert response.status_code == 302
    migrated = _refetch(migrated)
    assert migrated.script == 'Some Stranger; Bob Beta'
    assert _credits(migrated) == [ANNA]


@pytest.mark.django_db
def test_the_edit_page_shows_the_checkbox(client, indexer, migrated):
    """The row of a migrated credit has the checkbox on the real page."""
    response = client.get(reverse('edit_revision',
                                  kwargs={'id': migrated.id,
                                          'model_name': 'story'}))

    assert response.status_code == 200
    page = response.content.decode()
    assert 'name="story_credit_revisions-0-revert_migration"' in page
    assert '<i>Anna Alpha</i>' in page


@pytest.mark.django_db
def test_the_help_text_escapes_the_old_credit(issue_change,
                                              any_edit_story_rev, names):
    """Text from the old credit cannot add markup to the edit page."""
    revision = _migrated_with(any_edit_story_rev,
                              script='Anna Alpha (<b>plot</b>)')

    help_text = _rows(revision)[0].fields['revert_migration'].help_text

    assert '&lt;b&gt;plot' in help_text
    assert '<b>' not in help_text


@pytest.mark.django_db
def test_no_revert_on_an_added_sequence(any_added_story_rev, names):
    """A new sequence has no approved text to go back to."""
    any_added_story_rev.script = SCRIPT
    any_added_story_rev.save()
    any_added_story_rev.migrate_credits()

    assert len(_credits(any_added_story_rev)) == 2
    assert _offered(any_added_story_rev) == []


@pytest.mark.django_db
def test_no_revert_on_a_forked_sequence(any_added_story, issue_change, names):
    """A sequence copied from another one has no approved text either."""
    revision = StoryRevision.clone(any_added_story, issue_change, fork=True)
    revision.script = SCRIPT
    revision.save()
    revision.migrate_credits()

    assert len(_credits(revision)) == 2
    assert _offered(revision) == []


@pytest.mark.django_db
def test_no_revert_on_an_added_variant(any_added_variant_rev, names):
    """The approved text of the base issue is not the variant's own."""
    any_added_variant_rev.variant_of.revisions.update(editing='Anna Alpha')
    IssueCreditRevision.objects.create(
      changeset=any_added_variant_rev.changeset, credit_name='editor',
      issue_revision=any_added_variant_rev, creator=names['Anna Alpha'],
      credit_type_id=CREDIT_TYPES['editing'])

    assert _refetch(any_added_variant_rev).previous() is not None
    assert len(_credits(any_added_variant_rev)) == 1
    assert _offered(any_added_variant_rev) == []


@pytest.mark.django_db
def test_no_revert_of_a_credit_from_an_approved_change(migrated, names):
    """A row with a source was not migrated in this change."""
    row = migrated.story_credit_revisions.get(creator=names['Anna Alpha'])
    row.story_credit = StoryCredit.objects.create(
      story=migrated.story, creator=row.creator, credit_type=row.credit_type,
      signed_as='', credited_as='', sourced_by='', credit_name='')
    row.save()

    assert _offered(migrated) == [BOB]


@pytest.mark.django_db
def test_no_revert_of_a_sourced_credit(migrated, names):
    """Migration never sets a source, so an indexer has worked on the row."""
    row = migrated.story_credit_revisions.get(creator=names['Anna Alpha'])
    row.is_sourced = True
    row.sourced_by = 'an interview'
    row.save()

    assert _offered(migrated) == [BOB]


@pytest.mark.django_db
def test_no_revert_of_a_credit_with_a_signature(migrated, names):
    """Migration never picks a signature either."""
    row = migrated.story_credit_revisions.get(creator=names['Anna Alpha'])
    row.is_signed = True
    row.signature = CreatorSignature.objects.create(
      name='AA', creator=row.creator.creator, notes='', generic=True)
    row.save()

    assert _offered(migrated) == [BOB]


@pytest.mark.django_db
def test_no_revert_of_a_hand_added_credit(migrated):
    """A row for somebody not named in the old text cannot be traced."""
    StoryCreditRevision.objects.create(
      changeset=migrated.changeset, story_revision=migrated,
      creator=_creator('Carla Gamma'), credit_type_id=CREDIT_TYPES['script'])

    assert len(_credits(migrated)) == 3
    assert _offered(migrated) == [ANNA, BOB]


@pytest.mark.django_db
def test_no_revert_when_the_creator_is_in_two_credits(issue_change,
                                                      any_edit_story_rev,
                                                      names):
    """Two old credits of the same creator cannot be told apart."""
    revision = _migrated_with(any_edit_story_rev,
                              script='Anna Alpha; Anna Alpha (plot); Bob Beta')

    assert len(_credits(revision)) == 3
    assert _offered(revision) == [BOB]


@pytest.mark.django_db
def test_a_combination_is_judged_per_resulting_type(issue_change,
                                                    any_edit_story_rev, names):
    """The rows of a combined credit only trace to the text of their type."""
    revision = _migrated_with(any_edit_story_rev, pencils='Anna Alpha')
    StoryCreditRevision.objects.create(
      changeset=revision.changeset, story_revision=revision,
      creator=names['Anna Alpha'], credit_type_id=CREDIT_TYPES['inks'])

    assert len(_credits(revision)) == 2
    assert _offered(revision) == [('Anna Alpha', 'pencils')]


@pytest.mark.django_db
def test_a_later_edit_of_the_text_survives(client, indexer, migrated):
    """Text typed after the migration is kept next to the restored credit."""
    response = _save(client, indexer, migrated, revert=[ANNA],
                     script='Some Stranger; New Person')

    assert response.status_code == 302
    migrated = _refetch(migrated)
    assert migrated.script == 'Anna Alpha; Some Stranger; New Person'
    assert _credits(migrated) == [BOB]


@pytest.mark.django_db
def test_an_invalid_form_changes_nothing(client, indexer, migrated):
    """A form with errors reverts nothing, whatever is checked."""
    response = _save(client, indexer, migrated, revert=[ANNA],
                     page_count='not a number')

    assert response.status_code == 200
    assert 'Enter a number' in response.content.decode()
    migrated = _refetch(migrated)
    assert migrated.script == 'Some Stranger'
    assert _credits(migrated) == [ANNA, BOB]


@pytest.mark.django_db
def test_issue_editing_round_trip(client, indexer, migrated_issue):
    """The editing of an issue is migrated, then put back in the text."""
    assert migrated_issue.editing == 'Some Stranger'
    assert _offered(migrated_issue) == [('Anna Alpha', 'editing')]

    response = _save(client, indexer, migrated_issue,
                     revert=[('Anna Alpha', 'editing')])

    assert response.status_code == 302
    migrated_issue = _refetch(migrated_issue)
    assert migrated_issue.editing == 'Anna Alpha; Some Stranger'
    assert _credits(migrated_issue) == []


@pytest.mark.django_db
def test_reverting_everything_leaves_no_change(client, indexer, migrated):
    """After a full revert the comparison has nothing to report."""
    response = _save(client, indexer, migrated, revert=[ANNA, BOB])

    assert response.status_code == 302
    migrated = _refetch(migrated)
    assert migrated.script == SCRIPT
    assert _credits(migrated) == []
    migrated.compare_changes()
    assert migrated.is_changed is False


@pytest.mark.django_db
def test_save_and_migrate_refuses_a_checked_revert(client, indexer, migrated):
    """Migrating would silently undo the revert, so nothing is saved."""
    response = _save(client, indexer, migrated, revert=[ANNA],
                     button='save_migrate', title='Not saved')

    assert response.status_code == 200
    assert REFUSAL in response.content.decode()
    migrated = _refetch(migrated)
    assert migrated.script == 'Some Stranger'
    assert migrated.title != 'Not saved'
    assert _credits(migrated) == [ANNA, BOB]


@pytest.mark.django_db
def test_save_and_migrate_refuses_a_revert_on_an_issue(client, indexer,
                                                       migrated_issue):
    """The issue form refuses the combination in the same way."""
    response = _save(client, indexer, migrated_issue, revert=[ISSUE_ANNA],
                     button='save_migrate', notes='Not saved')

    assert response.status_code == 200
    assert REFUSAL in response.content.decode()
    migrated_issue = _refetch(migrated_issue)
    assert migrated_issue.editing == 'Some Stranger'
    assert migrated_issue.notes != 'Not saved'
    assert _credits(migrated_issue) == [ISSUE_ANNA]


@pytest.mark.django_db
def test_save_and_migrate_works_without_a_revert(client, indexer, migrated):
    """Only a checked revert stops Save And Migrate."""
    response = _save(client, indexer, migrated, button='save_migrate')

    assert response.status_code == 302
    assert _credits(_refetch(migrated)) == [ANNA, BOB]


@pytest.mark.django_db
@pytest.mark.parametrize('other_name', [False, True])
def test_no_revert_when_two_rows_could_claim_one_credit(
        issue_change, any_edit_story_rev, names, other_name):
    """A hand-added row of the creator, in any name, makes it ambiguous."""
    revision = _migrated_with(any_edit_story_rev, script='Anna Alpha')
    assert _offered(revision) == [ANNA]
    name = names['Anna Alpha']
    if other_name:
        name = CreatorNameDetail.objects.create(
          name='A. Alpha', creator=name.creator, in_script=name.in_script)
    StoryCreditRevision.objects.create(
      changeset=revision.changeset, story_revision=revision, creator=name,
      credit_type_id=CREDIT_TYPES['script'])

    assert len(_credits(revision)) == 2
    assert _offered(revision) == []


@pytest.mark.django_db
def test_no_revert_when_two_issue_rows_could_claim_one_credit(migrated_issue,
                                                              names):
    """The rows of an issue are counted in the same way."""
    assert _offered(migrated_issue) == [ISSUE_ANNA]
    IssueCreditRevision.objects.create(
      changeset=migrated_issue.changeset, issue_revision=migrated_issue,
      creator=names['Anna Alpha'], credit_name='assistant',
      credit_type_id=CREDIT_TYPES['editing'])

    assert len(_credits(migrated_issue)) == 2
    assert _offered(migrated_issue) == []


@pytest.mark.django_db
def test_a_row_with_a_source_cannot_claim_the_credit(migrated, names):
    """Only rows without a source compete for an old text credit."""
    name = names['Anna Alpha']
    StoryCreditRevision.objects.create(
      changeset=migrated.changeset, story_revision=migrated, creator=name,
      credit_type_id=CREDIT_TYPES['script'],
      story_credit=StoryCredit.objects.create(
        story=migrated.story, creator=name, signed_as='', credited_as='',
        credit_type_id=CREDIT_TYPES['script'], sourced_by='', credit_name=''))

    assert len(_credits(migrated)) == 3
    assert _offered(migrated) == [ANNA, BOB]


@pytest.mark.django_db
def test_revert_finds_a_neighbour_that_migration_renamed(
        client, indexer, issue_change, any_edit_story_rev, names):
    """Migration turns Typeset into typeset, which still follows the credit."""
    revision = _migrated_with(any_edit_story_rev,
                              letters='Anna Alpha; Typeset')
    assert revision.letters == 'typeset'

    response = _save(client, indexer, revision,
                     revert=[('Anna Alpha', 'letters')])

    assert response.status_code == 302
    assert _refetch(revision).letters == 'Anna Alpha; typeset'


@pytest.mark.django_db
@pytest.mark.parametrize('old, kept', [
    ('Some Stranger (plot)?', 'Some Stranger (plot)'),
    ('Some Stranger (plot)?', 'Some Stranger (plot)?'),
    ('Some  Stranger (plot)', 'Some Stranger (plot)')])
def test_revert_finds_a_neighbour_however_migration_left_it(
        client, indexer, issue_change, any_edit_story_rev, names, old, kept):
    """The ? after a note and double spaces may or may not have been kept."""
    revision = _migrated_with(any_edit_story_rev,
                              script='Anna Alpha; ' + old)
    StoryRevision.objects.filter(id=revision.id).update(script=kept)

    response = _save(client, indexer, revision, revert=[ANNA])

    assert response.status_code == 302
    assert _refetch(revision).script == 'Anna Alpha; ' + kept


@pytest.mark.django_db
@pytest.mark.parametrize('kept', ['Some Stranger (plot)',
                                  'Some Stranger (plot)?'])
def test_a_credit_left_in_the_text_is_recognised_however_written(
        issue_change, any_edit_story_rev, names, kept):
    """A credit which migration only rewrote has not gone from the text."""
    revision = _migrated_with(any_edit_story_rev,
                              script='Bob Beta; Some Stranger (plot)?')
    StoryRevision.objects.filter(id=revision.id).update(script=kept)
    StoryCreditRevision.objects.create(
      changeset=revision.changeset, story_revision=revision,
      creator=_creator('Some Stranger'),
      credit_type_id=CREDIT_TYPES['script'])

    assert len(_credits(revision)) == 2
    assert _offered(_refetch(revision)) == [BOB]


@pytest.mark.django_db
def test_no_revert_while_the_credit_is_still_in_the_text(migrated):
    """A credit typed back by hand has nothing left to restore."""
    StoryRevision.objects.filter(id=migrated.id).update(
      script='Anna Alpha; Some Stranger')

    assert _offered(_refetch(migrated)) == [BOB]


@pytest.mark.django_db
def test_revert_goes_between_the_credits_around_it(
        client, indexer, issue_change, any_edit_story_rev, names):
    """A credit goes back after the earlier credits, before the later."""
    revision = _migrated_with(any_edit_story_rev,
                              script='First One; Anna Alpha; Last One')
    assert revision.script == 'First One; Last One'

    response = _save(client, indexer, revision, revert=[ANNA])

    assert response.status_code == 302
    assert _refetch(revision).script == 'First One; Anna Alpha; Last One'


@pytest.mark.django_db
def test_remove_wins_over_revert_on_a_sequence(client, indexer, migrated):
    """A row checked for both is only removed."""
    response = _save(client, indexer, migrated, revert=[ANNA], remove=[ANNA])

    assert response.status_code == 302
    migrated = _refetch(migrated)
    assert migrated.script == 'Some Stranger'
    assert _credits(migrated) == [BOB]


@pytest.mark.django_db
def test_remove_wins_over_revert_on_an_issue(client, indexer, migrated_issue):
    """A row of an issue checked for both is only removed as well."""
    response = _save(client, indexer, migrated_issue, revert=[ISSUE_ANNA],
                     remove=[ISSUE_ANNA])

    assert response.status_code == 302
    migrated_issue = _refetch(migrated_issue)
    assert migrated_issue.editing == 'Some Stranger'
    assert _credits(migrated_issue) == []


@pytest.mark.django_db
@pytest.mark.parametrize('credit', [
    'Anna Alpha?', 'Anna  Alpha', 'Anna Alpha? (plot)',
    'Someone [as Anna Alpha]', 'Anna Alpha [as A.A.] (signed)'])
def test_revert_traces_every_way_of_writing_a_name(
        client, indexer, issue_change, any_edit_story_rev, names, credit):
    """The name is found wherever migration reads it in the credit."""
    revision = _migrated_with(any_edit_story_rev, script=credit)
    assert revision.script == ''
    assert _offered(revision) == [ANNA]

    response = _save(client, indexer, revision, revert=[ANNA])

    assert response.status_code == 302
    assert _refetch(revision).script == credit
