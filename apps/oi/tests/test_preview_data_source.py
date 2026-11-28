"""
The previews of creator-related objects don't show data sources removed in
the changeset, see #454.
"""

import pytest

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.gcd.models import (
    Creator, CreatorDegree, Degree, School, SourceType)
from apps.oi import states
from apps.oi.models import (
    Changeset, DataSourceRevision, CTYPES,
    CreatorArtInfluenceRevision, CreatorDegreeRevision,
    CreatorMembershipRevision, CreatorNonComicWorkRevision, CreatorRevision,
    CreatorSchoolRevision, ReceivedAwardRevision,
    PreviewCreator, PreviewCreatorArtInfluence, PreviewCreatorDegree,
    PreviewCreatorMembership, PreviewCreatorNonComicWork,
    PreviewCreatorSchool, PreviewReceivedAward)
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


@pytest.fixture
def creator_degree_with_source(any_indexer):
    """A creator degree with one data source, added via the OI."""
    creator = Creator.objects.create(
      gcd_official_name='Alex Example', sort_name='Example, Alex',
      bio='', notes='', birth_province='', birth_city='',
      death_province='', death_city='',
      birth_date=Date.objects.create(year='1940'),
      death_date=Date.objects.create())
    changeset = Changeset(state=states.OPEN, indexer=any_indexer,
                          change_type=CTYPES['creator_degree'])
    changeset.save()
    revision = CreatorDegreeRevision.objects.create(
      changeset=changeset, creator=creator,
      school=School.objects.create(school_name='Test School'),
      degree=Degree.objects.create(degree_name='Test Degree'),
      degree_year=1970, notes='')
    DataSourceRevision.objects.create(
      changeset=changeset, sourced_revision=revision,
      source_type=SourceType.objects.create(type='Test Source Type'),
      source_description='Source to be removed', field='')
    changeset.submit(notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.assign(approver=User.objects.get(id=any_indexer.id), notes='')
    changeset = Changeset.objects.get(id=changeset.id)
    changeset.approve(notes='')
    revision = CreatorDegreeRevision.objects.get(id=revision.id)
    return CreatorDegree.objects.get(id=revision.creator_degree.id)


@pytest.mark.django_db
def test_preview_does_not_show_removed_data_source(
        client, logged_in_indexer, creator_degree_with_source):
    creator_degree = creator_degree_with_source
    response = client.post(reverse('reserve_revision',
                                   kwargs={'model_name': 'creator_degree',
                                           'id': creator_degree.id}))
    assert response.status_code == 302
    changeset = Changeset.objects.get(
      state=states.OPEN, change_type=CTYPES['creator_degree'])
    revision = changeset.creatordegreerevisions.get()
    preview_url = reverse('preview_revision',
                          kwargs={'model_name': 'creator_degree',
                                  'id': revision.id})
    assert 'Source to be removed' in client.get(preview_url).content.decode()

    # the indexer empties the source fields, i.e. removes the data source
    response = client.post(
      reverse('process_revision', kwargs={'model_name': 'creator_degree',
                                          'id': revision.id}),
      {'school': creator_degree.school.id,
       'degree': creator_degree.degree.id,
       'degree_year': 1970,
       'notes': '',
       '_source_type': '',
       '_source_description': '',
       'comments': '',
       'save': 'Save'})
    assert response.status_code == 302
    assert changeset.datasourcerevisions.get().deleted is True

    response = client.get(preview_url)

    assert response.status_code == 200
    assert 'Source to be removed' not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('preview_class, revision_class', [
    (PreviewReceivedAward, ReceivedAwardRevision),
    (PreviewCreator, CreatorRevision),
    (PreviewCreatorSchool, CreatorSchoolRevision),
    (PreviewCreatorDegree, CreatorDegreeRevision),
    (PreviewCreatorMembership, CreatorMembershipRevision),
    (PreviewCreatorArtInfluence, CreatorArtInfluenceRevision),
    (PreviewCreatorNonComicWork, CreatorNonComicWorkRevision),
])
def test_preview_data_source_excludes_deleted(
        any_changeset, preview_class, revision_class):
    values = {
      'changeset': any_changeset,
      'revision_id': 1234,
      'content_type': ContentType.objects.get_for_model(revision_class),
      'source_type': SourceType.objects.create(type='Test Source Type'),
      'field': ''}
    kept = DataSourceRevision.objects.create(
      source_description='kept', deleted=False, **values)
    DataSourceRevision.objects.create(
      source_description='removed', deleted=True, **values)
    preview = preview_class()
    preview.revision = revision_class(id=1234)

    assert list(preview.data_source) == [kept]
