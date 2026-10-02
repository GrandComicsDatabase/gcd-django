import json
from unittest.mock import patch
from copy import deepcopy
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.template.loader import render_to_string

from apps.gcd.models import StoryType, CreditType
from apps.oi import states
from apps.oi.models import CTYPES, IssueRevision, StoryRevision
from apps.oi.sequence_workbench import (
    migrate_all_credits, save_sequences, sequence_snapshot, snapshot_version,
    workbench_context,
)


@pytest.fixture(autouse=True)
def reference_types(db):
    for pk, name in [(19, 'comic story'), (6, 'cover'),
                     (7, 'cover reprint (on interior page)'), (8, 'credits')]:
        StoryType.objects.get_or_create(pk=pk, defaults={'name': name, 'sort_code': pk})
    CreditType.objects.get_or_create(pk=6, defaults={'name': 'editing', 'sort_code': 6})


@pytest.fixture
def workbench(any_edit_story_rev, any_indexer):
    story = any_edit_story_rev
    changeset = story.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    issue = IssueRevision.clone(story.issue, changeset=changeset)
    any_indexer.user_permissions.add(Permission.objects.get(codename='can_reserve'))
    return changeset, issue, story, any_indexer


def payload(changeset):
    issues = sequence_snapshot(changeset)
    return {'issues': deepcopy(issues), 'version': snapshot_version(issues)}


def post(changeset, user, data):
    request = RequestFactory().post('/sequences/', json.dumps(data), content_type='application/json')
    request.user = user
    return save_sequences(request, changeset.pk)


def test_bulk_migration_only_active_legacy_credits(workbench):
    changeset, issue, story, user = workbench
    story.script = 'Legacy creator'
    story.save()
    deleted = StoryRevision.clone_revision(story, changeset, issue)
    deleted.deleted = True
    deleted.save()
    clean = StoryRevision.clone_revision(story, changeset, issue)
    for field in ('script', 'pencils', 'inks', 'colors', 'letters', 'editing'):
        setattr(clean, field, '')
    clean.save()
    request = RequestFactory().post('/migrate/')
    request.user = user
    with patch.object(StoryRevision, 'migrate_credits', autospec=True) as migrate:
        response = migrate_all_credits(request, changeset.pk)
    assert response.status_code == 302
    assert response.url == '/changeset/%s/edit/' % changeset.pk
    assert [call.args[0].pk for call in migrate.call_args_list] == [story.pk]
    html = render_to_string('oi/edit/issue_changeset.html', {
        'changeset': changeset, 'user': user, 'CTYPES': CTYPES,
        **workbench_context(changeset),
    })
    assert html.count('>Migrate credits</span>') == 1
    assert 'Migrate all credits <span data-migration-count>' in html


def test_inline_migration_returns_rows_and_checks_version(workbench):
    changeset, issue, story, user = workbench
    story.script = 'Legacy creator'
    story.save()
    data = {'version': snapshot_version(sequence_snapshot(changeset)), 'story': story.pk}

    def migrate(revision):
        revision.script = ''
        revision.save()

    request = RequestFactory().post('/migrate/', json.dumps(data), content_type='application/json')
    request.user = user
    with patch.object(StoryRevision, 'migrate_credits', autospec=True, side_effect=migrate) as converter:
        response = migrate_all_credits(request, changeset.pk)
    assert response.status_code == 200
    assert converter.call_count == 1
    result = json.loads(response.content)
    assert result['version'] == snapshot_version(sequence_snapshot(changeset))
    assert result['rows'][0]['id'] == story.pk
    assert 'data-row=' in result['rows'][0]['html']
    data['version'] = 'stale'
    request = RequestFactory().post('/migrate/', json.dumps(data), content_type='application/json')
    request.user = user
    assert migrate_all_credits(request, changeset.pk).status_code == 409


def test_migration_links_text_feature_like_production(workbench):
    from apps.gcd.models import Feature, FeatureNameDetail, FeatureType
    changeset, issue, story, user = workbench
    feature_type, _ = FeatureType.objects.get_or_create(pk=1, defaults={'name': 'feature'})
    feature = Feature.objects.create(name='Avengers', sort_name='Avengers',
                                     language=issue.series.language,
                                     feature_type=feature_type)
    name = FeatureNameDetail.objects.create(feature=feature, name='Avengers',
                                           sort_name='Avengers', is_official_name=True)
    story.feature = 'Avengers; Unknown Strip'
    story.save()
    request = RequestFactory().post('/migrate/')
    request.user = user
    assert migrate_all_credits(request, changeset.pk).status_code == 302
    story.refresh_from_db()
    assert list(story.feature_name.all()) == [name]
    assert story.feature == 'Unknown Strip'


def test_bulk_migration_access_and_post_only(workbench, django_user_model):
    changeset, issue, story, user = workbench
    request = RequestFactory().get('/migrate/')
    request.user = user
    assert migrate_all_credits(request, changeset.pk).status_code == 405
    request = RequestFactory().post('/migrate/')
    other = django_user_model.objects.create_user('other-migration')
    other.user_permissions.add(Permission.objects.get(codename='can_reserve'))
    request.user = other
    assert migrate_all_credits(request, changeset.pk).status_code == 403
    request.user = user
    changeset.state = states.PENDING
    changeset.save()
    assert migrate_all_credits(request, changeset.pk).status_code == 403


def test_bulk_migration_rolls_back_on_failure(workbench):
    changeset, issue, story, user = workbench
    story.script = 'Legacy creator'
    story.save()
    request = RequestFactory().post('/migrate/')
    request.user = user

    def fail(revision):
        revision.script = ''
        revision.save()
        raise ValueError('Migration failed')

    with patch.object(StoryRevision, 'migrate_credits', autospec=True, side_effect=fail):
        with pytest.raises(ValueError, match='Migration failed'):
            migrate_all_credits(request, changeset.pk)
    story.refresh_from_db()
    assert story.script == 'Legacy creator'


def test_edit_and_stale_draft_conflict(workbench):
    changeset, issue, story, user = workbench
    data = payload(changeset)
    data['issues'][0]['rows'][0].update(title='Updated', pages='3.33')
    response = post(changeset, user, data)
    assert response.status_code == 200, response.content
    story.refresh_from_db()
    assert story.title == 'Updated'
    assert story.page_count == Decimal('3.33')
    data['issues'][0]['rows'][0]['title'] = 'Stale overwrite'
    assert post(changeset, user, data).status_code == 409
    story.refresh_from_db()
    assert story.title == 'Updated'


@pytest.mark.parametrize('pages', ['-1', '0', 'NaN', 'Infinity', '0.0001', '10000000', ''])
def test_invalid_pages_roll_back(workbench, pages):
    changeset, issue, story, user = workbench
    story.page_count_uncertain = False
    story.save()
    data = payload(changeset)
    data['issues'][0]['rows'][0].update(title='Must not save', pages=pages)
    assert post(changeset, user, data).status_code == 400
    story.refresh_from_db()
    assert story.title != 'Must not save'


def test_foreign_rows_rejected(workbench):
    changeset, issue, story, user = workbench
    data = payload(changeset)
    data['issues'][0]['rows'][0]['id'] += 99999
    assert post(changeset, user, data).status_code == 400


def test_owner_and_state_enforced(workbench, django_user_model):
    changeset, issue, story, user = workbench
    other = django_user_model.objects.create_user('other')
    other.user_permissions.add(Permission.objects.get(codename='can_reserve'))
    assert post(changeset, other, payload(changeset)).status_code == 403
    changeset.state = states.PENDING
    changeset.save()
    assert post(changeset, user, payload(changeset)).status_code == 403


@pytest.mark.parametrize('replacement_type', [19, 7])
def test_retyped_cover_reordered_without_cover_starts_at_zero(workbench, replacement_type):
    changeset, issue, story, user = workbench
    cover = StoryRevision.clone_revision(story, changeset, issue)
    cover.type_id = 6
    cover.sequence_number = 0
    cover.save()
    data = payload(changeset)
    rows = data['issues'][0]['rows']
    moved = next(row for row in rows if row['id'] == cover.pk)
    moved['type'] = replacement_type
    rows.remove(moved)
    rows.append(moved)
    response = post(changeset, user, data)
    assert response.status_code == 200, response.content
    story.refresh_from_db()
    cover.refresh_from_db()
    assert story.sequence_number == 0
    assert cover.sequence_number == 1
    assert cover.type_id == replacement_type


def test_cover_zero_reprints_and_reorder(workbench):
    changeset, issue, story, user = workbench
    cover = StoryRevision.clone_revision(story, changeset, issue)
    cover.type_id = 6
    cover.page_count = 2
    cover.save()
    second = StoryRevision.clone_revision(cover, changeset, issue)
    second.type_id = 7
    second.save()
    data = payload(changeset)
    data['issues'][0]['rows'].reverse()
    assert post(changeset, user, data).status_code == 200
    cover.refresh_from_db()
    second.refresh_from_db()
    story.refresh_from_db()
    assert cover.sequence_number == 0
    assert second.sequence_number == 1
    assert story.sequence_number == 2


@pytest.mark.parametrize('type_id', [8, 22, 24, 25])
def test_no_feature_type_clears_legacy_feature(workbench, type_id):
    changeset, issue, story, user = workbench
    StoryType.objects.get_or_create(pk=type_id, defaults={'name': 'No feature type', 'sort_code': type_id})
    story.genre = ''
    story.save()
    data = payload(changeset)
    data['issues'][0]['rows'][0]['type'] = type_id
    response = post(changeset, user, data)
    assert response.status_code == 200, response.content
    story.refresh_from_db()
    assert story.feature == ''


def test_issue_page_count_uses_revision_including_unknown(workbench):
    changeset, issue, story, user = workbench
    issue.page_count = None
    issue.save()
    assert sequence_snapshot(changeset)[0]['declared'] is None
    issue.page_count = 120
    issue.save()
    assert Decimal(sequence_snapshot(changeset)[0]['declared']) == 120


def test_duplicate_preserves_all_scalar_fields(workbench):
    changeset, issue, story, user = workbench
    response = add_request(changeset, issue, user, duplicate=story.pk)
    assert response.status_code == 200, response.content
    duplicate = StoryRevision.objects.get(pk=json.loads(response.content)['row_id'])
    assert duplicate.pk != story.pk
    assert duplicate.story_id is None
    for field in StoryRevision._get_single_value_fields():
        if field not in ('sequence_number',):
            assert getattr(duplicate, field) == getattr(story, field), field
    assert duplicate.keywords == story.keywords


def test_duplicate_preserves_linked_creator_details(workbench):
    from apps.gcd.models import Creator, CreatorNameDetail
    from apps.stddata.models import Script
    from apps.oi.models import StoryCreditRevision
    changeset, issue, story, user = workbench
    creator = Creator.objects.create(gcd_official_name='Test Creator')
    script = Script.objects.create(code='Tst', number=999, name='Test Script')
    name = CreatorNameDetail.objects.create(name='Test Creator', creator=creator,
                                            is_official_name=True, in_script=script)
    credit = StoryCreditRevision.objects.create(
        changeset=changeset, story_revision=story, creator=name, credit_type_id=6,
        is_credited=True, credited_as='Pen name', uncertain=True,
        is_sourced=True, sourced_by='Publisher archive', credit_name='Editor')
    response = add_request(changeset, issue, user, duplicate=story.pk)
    assert response.status_code == 200, response.content
    duplicate = StoryRevision.objects.get(pk=json.loads(response.content)['row_id'])
    copied = duplicate.story_credit_revisions.get()
    assert copied.pk != credit.pk
    for field in ('creator_id', 'credit_type_id', 'is_credited', 'credited_as',
                  'uncertain', 'is_sourced', 'sourced_by', 'credit_name'):
        assert getattr(copied, field) == getattr(credit, field)


def test_multiple_feature_names_saved_as_objects(workbench):
    from apps.gcd.models import Feature, FeatureNameDetail, FeatureType
    changeset, issue, story, user = workbench
    feature_type, _ = FeatureType.objects.get_or_create(pk=1, defaults={'name': 'feature'})
    names = []
    for label in ('Avengers', 'Zagor'):
        feature = Feature.objects.create(name=label, sort_name=label,
                                         language=issue.series.language,
                                         feature_type=feature_type)
        names.append(FeatureNameDetail.objects.create(feature=feature, name=label,
                     sort_name=label, is_official_name=True))
    data = payload(changeset)
    data['issues'][0]['rows'][0].update(
        selected_features=[{'id': name.pk, 'text': str(name)} for name in names],
        feature_text='')
    response = post(changeset, user, data)
    assert response.status_code == 200, response.content
    story.refresh_from_db()
    assert story.feature == ''
    assert set(story.feature_name.values_list('pk', flat=True)) == {name.pk for name in names}
    data = payload(changeset)
    data['issues'][0]['rows'][0].update(selected_features=[], feature_text='New feature')
    assert post(changeset, user, data).status_code == 200
    story.refresh_from_db()
    assert story.feature == 'New feature'
    assert not story.feature_name.exists()


def test_copy_and_reprint_actions_use_existing_views(workbench):
    from django.urls import reverse
    changeset, issue, story, user = workbench
    html = render_to_string('oi/edit/issue_changeset.html', {
        **workbench_context(changeset), 'changeset': changeset,
        'user': user, 'CTYPES': CTYPES})
    assert reverse('add_story', kwargs={
        'issue_revision_id': issue.pk,
        'changeset_id': changeset.pk}) in html
    assert 'name="copy"' in html
    assert '>Add Reprint</a>' in html


def test_template_renders_actions_and_empty_table(workbench):
    changeset, issue, story, user = workbench
    context = dict(changeset=changeset, user=user, CTYPES=CTYPES,
                   **workbench_context(changeset))
    html = render_to_string('oi/edit/issue_changeset.html', context)
    assert 'Reorder Issue Sequences' not in html
    assert 'Duplicate Sequence' in html
    assert 'Drop file here or click to browse' in html
    assert 'data-row=' in html
    full_page = render_to_string('oi/edit/changeset.html', {
        **context, 'states': states,
        'workflow_action_labels': {'submit': 'Submit Changes For Approval'},
    })
    assert full_page.count('<h1') == 1
    story.delete()
    html = render_to_string('oi/edit/issue_changeset.html', context)
    assert 'No sequences yet.' in html


def test_linked_feature_preserved_then_cleared_inline(workbench):
    from apps.gcd.models import Feature, FeatureNameDetail, FeatureType
    changeset, issue, story, user = workbench
    feature_type, _ = FeatureType.objects.get_or_create(pk=1, defaults={'name': 'feature'})
    feature = Feature.objects.create(name='Avengers', sort_name='Avengers',
                                     language=issue.series.language,
                                     feature_type=feature_type, genre='', notes='')
    name = FeatureNameDetail.objects.create(feature=feature, name='Avengers',
                                           sort_name='Avengers', is_official_name=True)
    story.feature = ''
    story.save()
    story.feature_name.add(name)
    data = payload(changeset)
    assert 'Avengers' in data['issues'][0]['rows'][0]['feature']
    data['issues'][0]['rows'][0]['title'] = 'Title only'
    assert post(changeset, user, data).status_code == 200
    assert story.feature_name.filter(pk=name.pk).exists()
    data = payload(changeset)
    data['issues'][0]['rows'][0]['feature'] = ''
    data['issues'][0]['rows'][0]['selected_features'] = []
    assert post(changeset, user, data).status_code == 200
    assert not story.feature_name.exists()


def test_late_validation_failure_rolls_back_all_rows(workbench):
    changeset, issue, story, user = workbench
    second = StoryRevision.clone_revision(story, changeset, issue)
    data = payload(changeset)
    data['issues'][0]['rows'][0]['title'] = 'Must roll back'
    data['issues'][0]['rows'][1]['pages'] = '-2'
    assert post(changeset, user, data).status_code == 400
    story.refresh_from_db()
    second.refresh_from_db()
    assert story.title != 'Must roll back'
    assert second.page_count > 0


def add_request(changeset, issue, user, **overrides):
    from apps.oi.sequence_workbench import add_sequence
    data = {'issue': issue.pk, 'version': snapshot_version(sequence_snapshot(changeset))}
    data.update(overrides)
    request = RequestFactory().post('/sequences/add/', json.dumps(data), content_type='application/json')
    request.user = user
    return add_sequence(request, changeset.pk)


def test_add_inline_returns_editable_row_and_correct_issue(workbench):
    changeset, issue, story, user = workbench
    response = add_request(changeset, issue, user)
    assert response.status_code == 200, response.content
    result = json.loads(response.content)
    added = changeset.storyrevisions.get(pk=result['row_id'])
    assert added.issue_id == issue.issue_id
    assert added.page_count is None
    assert added.type_id == 19
    assert added.title == added.feature == ''
    assert 'data-field="title"' in result['row_html']
    from django.urls import reverse
    assert reverse('edit_revision', kwargs={'model_name': 'story', 'id': added.pk}) in result['row_html']
    assert 'Location' not in response


def test_first_inline_sequence_defaults_to_cover_without_page_total(workbench):
    changeset, issue, story, user = workbench
    story.delete()
    issue.page_count = None
    issue.save()
    issue.issue.page_count = None
    issue.issue.save()
    response = add_request(changeset, issue, user)
    assert response.status_code == 200, response.content
    result = json.loads(response.content)
    assert result['issues'][0]['declared'] is None
    added = changeset.storyrevisions.get(pk=result['row_id'])
    assert added.type_id == 6
    assert added.sequence_number == 0
    assert added.page_count is None


def test_new_sequence_without_pages_does_not_block_other_rows(workbench):
    changeset, issue, story, user = workbench
    assert add_request(changeset, issue, user).status_code == 200
    data = payload(changeset)
    data['issues'][0]['rows'][0]['title'] = 'Saved anyway'
    response = post(changeset, user, data)
    assert response.status_code == 200, response.content
    story.refresh_from_db()
    assert story.title == 'Saved anyway'


def test_inline_add_rejects_missing_issue_and_stale_version(workbench):
    changeset, issue, story, user = workbench
    assert add_request(changeset, issue, user, version='stale').status_code == 409
    issue.issue = None
    issue.save()
    assert add_request(changeset, issue, user).status_code == 400
    assert changeset.storyrevisions.count() == 1


def test_inline_add_rejects_other_owner_and_closed_changeset(workbench, django_user_model):
    changeset, issue, story, user = workbench
    other = django_user_model.objects.create_user('other-inline')
    other.user_permissions.add(Permission.objects.get(codename='can_reserve'))
    assert add_request(changeset, issue, other).status_code == 403
    changeset.state = states.PENDING
    changeset.save()
    assert add_request(changeset, issue, user).status_code == 403


def test_type_change_preserves_genre_as_text(workbench):
    changeset, issue, story, user = workbench
    original_genre = story.genre
    data = payload(changeset)
    data['issues'][0]['rows'][0]['type'] = 7
    assert post(changeset, user, data).status_code == 200
    story.refresh_from_db()
    assert story.genre == original_genre


def test_type_change_rejects_incompatible_hidden_genre_atomically(workbench):
    changeset, issue, story, user = workbench
    data = payload(changeset)
    data['issues'][0]['rows'][0]['type'] = 8
    response = post(changeset, user, data)
    assert response.status_code == 400
    assert b'cannot have a genre' in response.content
    story.refresh_from_db()
    assert story.type_id == 19
    assert story.feature == 'Test Feature'


def test_credit_colors_preserve_legacy_complete_and_incomplete_states(workbench):
    from apps.oi.templatetags.compare import show_credit_status
    changeset, issue, story, user = workbench
    assert 'text-green-500' in show_credit_status(story)
    story.script = ''
    story.no_script = False
    assert 'text-red-500' in show_credit_status(story)
    story.no_script = True
    assert 'text-green-500' in show_credit_status(story)


def test_hidden_type_rule_matches_full_editor(workbench):
    from apps.oi.views import validate_revision_for_transition
    changeset, issue, story, user = workbench
    story.type_id = 8
    story.feature = ''
    story.save()
    request = RequestFactory().post('/edit/')
    request.user = user
    messages = validate_revision_for_transition(story, request)
    assert 'The sequence type cannot have a genre.' in messages


def test_insert_accepts_unknown_page_count_inline(workbench):
    changeset, issue, story, user = workbench
    StoryType.objects.get_or_create(pk=11, defaults={'name': 'insert or dust jacket', 'sort_code': 11})
    story.page_count_uncertain = False
    story.save()
    data = payload(changeset)
    data['issues'][0]['rows'][0].update(type=11, pages='')
    response = post(changeset, user, data)
    assert response.status_code == 200, response.content
    story.refresh_from_db()
    assert story.page_count is None


def test_inline_type_change_rejects_existing_story_arc(workbench):
    from apps.gcd.models import StoryArc
    changeset, issue, story, user = workbench
    arc = StoryArc.objects.create(name='Arc', sort_name='Arc', language=issue.series.language)
    story.story_arc.add(arc)
    data = payload(changeset)
    data['issues'][0]['rows'][0]['type'] = 7
    response = post(changeset, user, data)
    assert response.status_code == 400
    assert b'cannot have a story arc' in response.content
    story.refresh_from_db()
    assert story.type_id == 19
    assert story.story_arc.filter(pk=arc.pk).exists()
