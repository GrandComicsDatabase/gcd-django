import pytest

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.oi import states
from apps.oi.models import Changeset, CTYPES, IssueRevision, StoryRevision

TAB_BAR = 'nav-tabs'


@pytest.fixture
def story_revision(client, any_indexer, any_added_story):
    """A sequence in an open change of its issue, with its editor logged in."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)
    changeset = Changeset.objects.create(
      state=states.OPEN, indexer=any_indexer, change_type=CTYPES['issue'])
    IssueRevision.clone(data_object=any_added_story.issue,
                        changeset=changeset)
    return StoryRevision.clone(data_object=any_added_story,
                               changeset=changeset)


def _edit_page(client, revision):
    response = client.get(reverse('edit_revision',
                                  kwargs={'model_name': 'story',
                                          'id': revision.id}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('title, title_inferred, shown', [
    ('The Last Page', False, 'The Last Page'),
    ('The Last Page', True, '[The Last Page]'),
    ('', False, '[no title indexed]'),
    ('<b>Bold</b>', False, '&lt;b&gt;Bold&lt;/b&gt;'),
])
def test_tabbed_view_names_the_sequence_above_the_tabs(
  client, story_revision, title, title_inferred, shown):
    story_revision.sequence_number = 7
    story_revision.title = title
    story_revision.title_inferred = title_inferred
    story_revision.save()

    page = _edit_page(client, story_revision)

    heading = f'<h2>Sequence 7: {shown}</h2>'
    assert heading in page
    assert page.index(heading) < page.index(TAB_BAR)


@pytest.mark.django_db
def test_view_without_tabs_has_no_sequence_heading(client, any_indexer,
                                                   story_revision):
    any_indexer.indexer.use_tabs = False
    any_indexer.indexer.save()

    page = _edit_page(client, story_revision)

    assert TAB_BAR not in page
    assert '<h2>Sequence' not in page
