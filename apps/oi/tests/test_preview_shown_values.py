"""
Pages show the values of the approved object, previews and downloads of a
revision those of its changeset: data sources, brand emblems, feature
names, story arcs and universes.  The preview classes override methods of
the models for this and no longer shadow their fields, see #454.
"""

import re

import pytest

from django.contrib.auth.models import User
from django.urls import reverse

from apps.gcd.models import (
    Award, Creator, Degree, Feature, FeatureNameDetail, FeatureType,
    MembershipType, NonComicWorkRole, NonComicWorkType, School, SourceType,
    StoryArc, Universe)
from apps.oi import states
from apps.oi.import_export import BRAND
from apps.oi.models import (
    Changeset, DataSourceRevision, IssueRevision, CTYPES,
    CreatorArtInfluenceRevision, CreatorDegreeRevision,
    CreatorMembershipRevision, CreatorNonComicWorkRevision,
    CreatorSchoolRevision, ReceivedAwardRevision)
from apps.stddata.models import Date


@pytest.fixture
def logged_in_indexer(client, any_indexer):
    # superuser passes the permission checks of the OI views, enough
    # reservations so that the open changesets of the fixtures don't count
    any_indexer.is_superuser = True
    any_indexer.save()
    any_indexer.indexer.max_reservations = 10
    any_indexer.indexer.save()
    client.force_login(any_indexer)
    return any_indexer


def _content(client, url):
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


def _reserve(client, model_name, shown):
    """Reserve the object as an indexer does, return the new changeset."""
    response = client.post(reverse('reserve_revision',
                                   kwargs={'model_name': model_name,
                                           'id': shown.id}))
    assert response.status_code == 302
    return Changeset.objects.get(state=states.OPEN,
                                 change_type=CTYPES[model_name])


def _preview(client, model_name, revision):
    return _content(client, reverse('preview_revision',
                                    kwargs={'model_name': model_name,
                                            'id': revision.id}))


def _approve(changeset, approver):
    changeset.submit(notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.assign(approver=User.objects.get(id=approver.id), notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.approve(notes='')


def _creator():
    return Creator.objects.create(
      gcd_official_name='Some Creator', sort_name='Creator, Some',
      bio='', notes='', birth_province='', birth_city='',
      death_province='', death_city='',
      birth_date=Date.objects.create(year='1940'),
      death_date=Date.objects.create())


# the revision class and the values of each object with data sources
SOURCED = {
  'received_award': (ReceivedAwardRevision, lambda creator: {
    'recipient': creator,
    'award': Award.objects.create(name='Test Award', notes=''),
    'award_name': 'Test Prize', 'award_year': 1970, 'notes': ''}),
  'creator_school': (CreatorSchoolRevision, lambda creator: {
    'creator': creator,
    'school': School.objects.create(school_name='Test School'),
    'notes': ''}),
  'creator_degree': (CreatorDegreeRevision, lambda creator: {
    'creator': creator,
    'school': School.objects.create(school_name='Test School'),
    'degree': Degree.objects.create(degree_name='Test Degree'),
    'notes': ''}),
  'creator_membership': (CreatorMembershipRevision, lambda creator: {
    'creator': creator, 'organization_name': 'Test Organization',
    'membership_type': MembershipType.objects.create(type='Test Type'),
    'notes': ''}),
  'creator_art_influence': (CreatorArtInfluenceRevision, lambda creator: {
    'creator': creator, 'influence_name': 'Test Influence', 'notes': ''}),
  'creator_non_comic_work': (CreatorNonComicWorkRevision, lambda creator: {
    'creator': creator,
    'work_type': NonComicWorkType.objects.create(type='Test Work Type'),
    'publication_title': 'Test Publication',
    'work_role': NonComicWorkRole.objects.create(role_name='Test Role'),
    'notes': ''}),
}


@pytest.mark.django_db
@pytest.mark.parametrize('model_name', SOURCED)
def test_page_and_preview_show_their_own_data_source(
        client, logged_in_indexer, model_name):
    revision_class, values = SOURCED[model_name]
    changeset = Changeset(state=states.OPEN, indexer=logged_in_indexer,
                          change_type=CTYPES[model_name])
    changeset.save()
    revision = revision_class.objects.create(changeset=changeset,
                                             **values(_creator()))
    DataSourceRevision.objects.create(
      changeset=changeset, sourced_revision=revision,
      source_type=SourceType.objects.create(type='Test Source Type'),
      source_description='Approved source', field='')
    _approve(changeset, logged_in_indexer)
    shown = revision_class.objects.get(id=revision.id).source
    changeset = _reserve(client, model_name, shown)
    source = changeset.datasourcerevisions.get()
    source.source_description = 'Changed source'
    source.save()

    preview = _preview(client, model_name,
                       revision_class.objects.get(changeset=changeset))
    page = _content(client, shown.get_absolute_url())

    assert 'Changed source' in preview
    assert 'Approved source' not in preview
    assert 'Approved source' in page
    assert 'Changed source' not in page


def _feature_name(name, genre, language):
    feature = Feature.objects.create(
      name=name, sort_name=name, genre=genre, language=language,
      feature_type=FeatureType.objects.get_or_create(name='Test Type')[0],
      description='', notes='')
    return FeatureNameDetail.objects.create(
      feature=feature, name=name, sort_name=name, is_official_name=True)


def _story_arc(name, language):
    return StoryArc.objects.create(name=name, sort_name=name,
                                   language=language, description='',
                                   notes='')


def _universe(name):
    return Universe.objects.create(multiverse='', name=name,
                                   designation='', description='',
                                   notes='')


def _brand_cell(content):
    """The cell of the brand emblems in the issue data."""
    return re.search(r"Publisher's Brand:</span>(.*?)</li>", content,
                     re.S).group(1)


@pytest.mark.django_db
def test_issue_page_and_preview_show_their_own_values(
        client, logged_in_indexer, any_added_story, any_language,
        any_added_brand, second_brand_same_group):
    story = any_added_story
    issue = story.issue
    story.feature_name.add(_feature_name('Approved Feature Name', 'romance',
                                         any_language))
    story.story_arc.add(_story_arc('Approved Story Arc', any_language))
    story.universe.add(_universe('Approved Universe'))
    changeset = _reserve(client, 'issue', issue)
    issue_revision = changeset.issuerevisions.get()
    issue_revision.brand_emblem.set([second_brand_same_group])
    story_revision = changeset.storyrevisions.get()
    story_revision.feature_name.set([
      _feature_name('Changed Feature Name', 'western', any_language)])
    story_revision.story_arc.set([_story_arc('Changed Story Arc',
                                             any_language)])
    story_revision.universe.set([_universe('Changed Universe')])

    preview = _preview(client, 'issue', issue_revision)
    page = _content(client, issue.get_absolute_url())

    for shown, approved in [(page, True), (preview, False)]:
        for value in ['Feature Name', 'Story Arc', 'Universe']:
            assert ('Approved ' + value in shown) is approved
            assert ('Changed ' + value in shown) is not approved
        # the genre of the feature is added to the genre of the story
        assert ('romance' in shown) is approved
        assert ('western' in shown) is not approved
    assert any_added_brand.get_absolute_url() in _brand_cell(page)
    assert second_brand_same_group.name not in _brand_cell(page)
    assert second_brand_same_group.name in _brand_cell(preview)
    assert any_added_brand.get_absolute_url() not in _brand_cell(preview)


@pytest.mark.django_db
def test_a_downloaded_revision_has_the_brand_emblem_of_the_revision(
        client, logged_in_indexer, any_added_issue, any_editing_changeset,
        second_brand_same_group):
    revision = IssueRevision.clone(data_object=any_added_issue,
                                   changeset=any_editing_changeset)
    revision.brand_emblem.set([second_brand_same_group])

    response = client.get(reverse('export_issue_revision',
                                  kwargs={'issue_id': revision.id}))

    assert response.status_code == 200
    issue_line = response.content.decode().split('\r\n')[0].split('\t')
    assert issue_line[BRAND] == second_brand_same_group.name
