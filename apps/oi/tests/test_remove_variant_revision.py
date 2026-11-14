import pytest

from django.contrib.auth.models import User
from django.urls import reverse

from apps.gcd.models import (
    CodeNumberType, Creator, CreatorNameDetail, CreditType, ExternalSite,
    Issue, Story, StoryType)
from apps.indexer.models import Error
from apps.oi import states
from apps.oi.models import (
    Changeset, ChangesetComment, CoverRevision, CTYPES, ExternalLinkRevision,
    IssueCreditRevision, IssueRevision, PublisherCodeNumberRevision,
    RevisionLock, StoryRevision)
from apps.stddata.models import Script

ADD_BUTTON = 'Add Variant Issue'
REMOVE_BUTTON = 'Remove New Variant'


@pytest.fixture
def logged_in_indexer(client, any_indexer):
    """The holder of the changeset; a superuser passes the OI permissions."""
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    return any_indexer


@pytest.fixture
def base_issue(any_added_story):
    """An approved issue with one sequence and a variant name of its own."""
    issue = Issue.objects.get(id=any_added_story.issue_id)
    issue.variant_name = 'Regular'
    issue.save()
    return issue


@pytest.fixture
def issue_changeset(client, logged_in_indexer, base_issue):
    """The open changeset of the reserved base issue, holding its locks."""
    response = client.post(reverse(
      'reserve_revision', kwargs={'model_name': 'issue', 'id': base_issue.id}))
    assert response.status_code == 302
    return Changeset.objects.get(state=states.OPEN,
                                 change_type=CTYPES['issue'])


def _new_variant(changeset, base_issue):
    """Add a revision of a new variant of the base issue to the changeset."""
    return IssueRevision.objects.create(
      changeset=changeset, series=base_issue.series,
      variant_of=base_issue, variant_name='Shiny', number=base_issue.number,
      indicia_publisher=base_issue.indicia_publisher,
      no_title=True, no_volume=True, no_isbn=True, no_rating=True,
      no_brand=True, no_indicia_frequency=True,
      publication_date='February 1947', key_date='1947-02-00', page_count=32)


@pytest.fixture
def variant(issue_changeset, base_issue):
    """A new variant in the changeset, as Add Variant Issue leaves it."""
    revision = _new_variant(issue_changeset, base_issue)
    issue_changeset.change_type = CTYPES['variant_add']
    issue_changeset.save()
    return revision


def _add_sequence(variant, title='Extra Cover'):
    """Add a new sequence to the variant, tied to it only by issue=None."""
    return StoryRevision.objects.create(
      changeset=variant.changeset, issue=None, sequence_number=0,
      type=StoryType.objects.get(name='comic story'), title=title,
      page_count=1, script='Writer', pencils='Penciller', inks='Inker',
      no_colors=True, letters='Letterer', no_editing=True)


def _add_credit_code_and_link(variant):
    """Give the variant a credit, a publisher code and an external link."""
    changeset = variant.changeset
    creator = Creator.objects.create(
      gcd_official_name='Test Creator', birth_province='', birth_city='',
      death_province='', death_city='', bio='', notes='')
    script = Script.objects.create(code='Tst', number=999, name='Test Script')
    name = CreatorNameDetail.objects.create(
      name='Test Creator', creator=creator, is_official_name=True,
      in_script=script)
    IssueCreditRevision.objects.create(
      changeset=changeset, issue_revision=variant, creator=name,
      credit_type=CreditType.objects.create(name='test credit',
                                            sort_code=999))
    PublisherCodeNumberRevision.objects.create(
      changeset=changeset, issue_revision=variant, number='C1',
      number_type=CodeNumberType.objects.create(name='test code'))
    ExternalLinkRevision.objects.create(
      changeset=changeset, object_revision=variant,
      site=ExternalSite.objects.create(site='Test', matching='example.com'),
      link='https://example.com/variant')


def _comment_on(revision, commenter, text):
    """Attach a comment to the revision, as its edit form does."""
    return revision.comments.create(
      commenter=commenter, changeset=revision.changeset, text=text,
      old_state=states.OPEN, new_state=states.OPEN)


def _base_revision(variant):
    """Return the revision of the base issue next to the variant."""
    return IssueRevision.objects.filter(
      changeset=variant.changeset_id).exclude(id=variant.id).get()


def _url(revision):
    """Return the URL that removes the revision."""
    return reverse('remove_variant_revision', kwargs={'id': revision.id})


def _edit_url(changeset):
    """Return the URL of the edit page of the changeset."""
    return reverse('edit', kwargs={'id': changeset.id})


def _edit_page(client, changeset):
    """Return the content of the edit page, which has to load."""
    response = client.get(_edit_url(changeset))
    assert response.status_code == 200
    return response.content.decode()


def _contents(changeset):
    """All that a refused or cancelled removal has to leave untouched."""
    changeset = Changeset.objects.get(id=changeset.id)
    return (
      changeset.state, changeset.change_type,
      list(changeset.issuerevisions.order_by('id')
           .values_list('id', 'variant_name')),
      list(changeset.storyrevisions.order_by('id')
           .values_list('id', 'issue_id', 'story_id')),
      list(changeset.comments.order_by('id')
           .values_list('id', 'text', 'revision_id')),
      changeset.issuecreditrevisions.count(),
      changeset.publishercodenumberrevisions.count(),
      changeset.externallinkrevisions.count(),
      RevisionLock.objects.filter(changeset=changeset).count())


def _assert_refused(response, message):
    """Check that the response redirects to the given error message."""
    assert response.status_code == 302
    key = response['Location'].split('error_key=')[1]
    assert message in Error.objects.get(error_key=key).error_text


@pytest.mark.django_db
def test_button_is_on_the_new_variant_only(client, variant):
    """The edit page offers the removal for the new variant alone."""
    content = _edit_page(client, variant.changeset)
    assert content.count(REMOVE_BUTTON) == 1
    assert _url(variant) in content
    assert ADD_BUTTON not in content


@pytest.mark.django_db
def test_no_button_on_a_plain_issue_edit(client, issue_changeset):
    """An edit without a variant does not offer the removal."""
    content = _edit_page(client, issue_changeset)
    assert REMOVE_BUTTON not in content
    assert ADD_BUTTON in content


@pytest.mark.django_db
def test_no_button_on_a_variant_added_on_its_own(client, logged_in_indexer,
                                                 base_issue):
    """A variant added without its base issue is out of scope."""
    changeset = Changeset.objects.create(
      indexer=logged_in_indexer, state=states.OPEN,
      change_type=CTYPES['issue_add'])
    revision = _new_variant(changeset, base_issue)
    assert REMOVE_BUTTON not in _edit_page(client, changeset)
    before = _contents(changeset)
    _assert_refused(client.post(_url(revision)), 'Only a new variant')
    assert _contents(changeset) == before


@pytest.mark.django_db
def test_two_issues_changeset_is_out_of_scope(
        client, logged_in_indexer, base_issue, any_added_variant):
    """An existing variant edited with its base cannot be removed."""
    response = client.post(reverse(
      'reserve_two_issues', kwargs={'issue_one_id': base_issue.id,
                                    'issue_two_id': any_added_variant.id}))
    assert response.status_code == 302
    changeset = Changeset.objects.get(state=states.OPEN,
                                      change_type=CTYPES['two_issues'])
    assert REMOVE_BUTTON not in _edit_page(client, changeset)
    before = _contents(changeset)
    variant = changeset.issuerevisions.get(variant_of__isnull=False)
    _assert_refused(client.post(_url(variant)), 'Only a new variant')
    assert _contents(changeset) == before


@pytest.mark.django_db
def test_get_names_the_sequences_and_changes_nothing(client, variant):
    """The confirmation page names the sequences, nothing is removed."""
    _add_sequence(variant)
    before = _contents(variant.changeset)
    response = client.get(_url(variant))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Extra Cover' in content
    assert 'Confirm removal of variant' in content
    assert _contents(variant.changeset) == before


@pytest.mark.django_db
def test_cancel_returns_to_the_changeset_and_changes_nothing(client, variant):
    """Cancel goes back to the edit page and nothing is removed."""
    _add_sequence(variant)
    before = _contents(variant.changeset)
    response = client.post(_url(variant), {'cancel': 'Cancel'})
    assert response.status_code == 302
    assert response['Location'] == _edit_url(variant.changeset)
    assert _contents(variant.changeset) == before


def _log_in_someone_else(client, variant):
    """Refused case: someone other than the holder asks for the removal."""
    client.force_login(User.objects.create_superuser(
      'other', 'other@example.com', 'other'))


def _submit_changeset(client, variant):
    """Refused case: the changeset is no longer open."""
    Changeset.objects.filter(id=variant.changeset_id).update(
      state=states.PENDING)


def _make_it_an_issue_add(client, variant):
    """Refused case: the changeset is not a variant_add one."""
    Changeset.objects.filter(id=variant.changeset_id).update(
      change_type=CTYPES['issue_add'])


def _move_a_cover(client, variant):
    """Refused case: the changeset holds a cover revision."""
    CoverRevision.objects.create(changeset=variant.changeset,
                                 issue=variant.variant_of)


def _move_a_sequence(client, variant):
    """Refused case: a sequence of the base issue was moved to the variant."""
    StoryRevision.objects.filter(changeset=variant.changeset_id).update(
      issue=None)


@pytest.mark.django_db
@pytest.mark.parametrize('prepare, message', [
    (_log_in_someone_else, 'Only the reservation holder'),
    (_submit_changeset, 'no longer open'),
    (_make_it_an_issue_add, 'Only a new variant'),
    (_move_a_cover, 'undo the cover move'),
    (_move_a_sequence, 'Move To Other Issue')])
def test_refusals_change_nothing(client, variant, prepare, message):
    """Each refused case shows its message, on GET and on POST."""
    prepare(client, variant)
    before = _contents(variant.changeset)
    _assert_refused(client.get(_url(variant)), message)
    _assert_refused(client.post(_url(variant)), message)
    assert _contents(variant.changeset) == before


@pytest.mark.django_db
def test_base_revision_cannot_be_removed(client, variant):
    """Only the variant can be removed, not the revision of its base."""
    before = _contents(variant.changeset)
    _assert_refused(client.post(_url(_base_revision(variant))),
                    'Only a new variant')
    assert _contents(variant.changeset) == before


@pytest.mark.django_db
def test_removal_leaves_only_the_base_revision(client, variant):
    """The variant and all that hangs on it go, the base edit stays."""
    _add_credit_code_and_link(variant)
    _add_sequence(variant)
    changeset = variant.changeset
    base_revision = _base_revision(variant)
    base_sequence = changeset.storyrevisions.get(issue=base_revision.issue)
    locks = RevisionLock.objects.filter(changeset=changeset).count()
    assert locks == 2

    response = client.post(_url(variant))

    assert response.status_code == 302
    assert response['Location'] == _edit_url(changeset)
    changeset = Changeset.objects.get(id=changeset.id)
    assert changeset.change_type == CTYPES['issue']
    assert changeset.issuerevisions.get() == base_revision
    assert changeset.storyrevisions.get() == base_sequence
    assert changeset.issuecreditrevisions.count() == 0
    assert changeset.publishercodenumberrevisions.count() == 0
    assert changeset.externallinkrevisions.count() == 0
    assert RevisionLock.objects.filter(changeset=changeset).count() == locks
    content = _edit_page(client, changeset)
    assert ADD_BUTTON in content
    assert REMOVE_BUTTON not in content


@pytest.mark.django_db
def test_removal_keeps_every_comment(client, variant, logged_in_indexer):
    """Comments of the variant and its sequences stay on the changeset."""
    sequence = _add_sequence(variant)
    changeset = variant.changeset
    before = changeset.comments.count()
    _comment_on(variant, logged_in_indexer, 'on the variant')
    _comment_on(variant, logged_in_indexer, 'again on the variant')
    _comment_on(sequence, logged_in_indexer, 'on the sequence')

    client.post(_url(variant))

    assert changeset.comments.count() == before + 3
    for text, kind in [('on the variant', 'IssueRevision'),
                       ('again on the variant', 'IssueRevision'),
                       ('on the sequence', 'StoryRevision')]:
        comment = ChangesetComment.objects.get(changeset=changeset,
                                               text__startswith=text)
        assert comment.revision_id is None
        assert '\nThe %s "' % kind in comment.text
        assert 'was removed.' in comment.text
        assert '<span' not in comment.text
    assert 'again on the variant' in _edit_page(client, changeset)


@pytest.mark.django_db
@pytest.mark.parametrize('with_approver, added', [(True, 1), (False, 0)])
def test_approver_is_told_when_there_is_no_comment(
        client, variant, logged_in_indexer, with_approver, added):
    """Without comments a note tells the approver, if there is one."""
    changeset = variant.changeset
    if with_approver:
        Changeset.objects.filter(id=changeset.id).update(
          approver=logged_in_indexer)
    before = changeset.comments.count()

    client.post(_url(variant))

    assert changeset.comments.count() == before + added
    if with_approver:
        assert changeset.comments.filter(
          text='The IssueRevision "%s" was removed.' % variant).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('commented, notes', [('variant', 0), ('sequence', 1)])
def test_approver_note_depends_on_a_comment_on_the_variant(
        client, variant, logged_in_indexer, commented, notes):
    """Only a comment on the variant itself makes the note unnecessary."""
    sequence = _add_sequence(variant)
    changeset = variant.changeset
    Changeset.objects.filter(id=changeset.id).update(
      approver=logged_in_indexer)
    _comment_on(variant if commented == 'variant' else sequence,
                logged_in_indexer, 'A comment')

    client.post(_url(variant))

    assert changeset.comments.filter(
      text='The IssueRevision "%s" was removed.' % variant).count() == notes


@pytest.mark.django_db
def test_approval_after_removal_is_a_plain_issue_edit(
        client, variant, logged_in_indexer, base_issue):
    """Approval puts no sequence on the base and gives no add bonus."""
    _add_sequence(variant)
    changeset = variant.changeset
    base_revision = _base_revision(variant)
    base_revision.notes = 'Edited'
    base_revision.save()

    client.post(_url(variant))

    changeset = Changeset.objects.get(id=changeset.id)
    changeset.submit(notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.assign(approver=User.objects.get(id=logged_in_indexer.id),
                     notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.approve(notes='')

    changeset = Changeset.objects.get(id=changeset.id)
    assert changeset.state == states.APPROVED
    assert changeset.imps > 0
    assert changeset.total_imps() == changeset.imps
    issue = Issue.objects.get(id=base_issue.id)
    assert issue.notes == 'Edited'
    assert issue.variant_set.count() == 0
    assert Story.objects.filter(issue=issue).count() == 1


def _mistype_base_variant_name(variant):
    """Change the variant name in the base revision and return the latter."""
    base_revision = _base_revision(variant)
    base_revision.variant_name = 'Typed by mistake'
    base_revision.save()
    return base_revision


@pytest.mark.django_db
def test_base_variant_name_restored_without_other_variants(client, variant):
    """Without other variants the field is hidden again, so it is reset."""
    base_revision = _mistype_base_variant_name(variant)
    client.post(_url(variant))
    base_revision.refresh_from_db()
    assert base_revision.variant_name == 'Regular'


@pytest.mark.django_db
def test_base_variant_name_kept_with_other_variants(client, variant,
                                                    any_added_variant):
    """With other variants the field stays visible, so the edit stays."""
    base_revision = _mistype_base_variant_name(variant)
    client.post(_url(variant))
    base_revision.refresh_from_db()
    assert base_revision.variant_name == 'Typed by mistake'
