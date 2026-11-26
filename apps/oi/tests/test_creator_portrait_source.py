"""
The source of the portrait of a creator, entered in the creator change
like the source of the biography.
"""
import pytest

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.gcd.models import SourceType
from apps.oi.forms import ExternalLinkRevisionFormSet
from apps.oi.forms.creator import CreatorRevisionFormSet
from apps.oi.models import CreatorRevision, DataSourceRevision
from apps.stddata.models import Script

BOTH_SET = 'Source description and source type must both be set.'


@pytest.fixture(autouse=True)
def latin_script(db):
    """The script that a creator name has by default."""
    Script.objects.get_or_create(
      id=Script.LATIN_PK,
      defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})


@pytest.fixture
def source_type(db):
    """A source type of the list that the migrations load."""
    return SourceType.objects.get_or_create(type="Publisher's records")[0]


@pytest.fixture
def creator_client(any_indexer):
    """A client of an indexer who may add creators."""
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client = Client()
    client.force_login(any_indexer)
    return client


def _add_creator(client, **portrait_source):
    """Post a new creator with the portrait_source fields given."""
    names = CreatorRevisionFormSet().prefix
    links = ExternalLinkRevisionFormSet().prefix
    data = {f'{names}-TOTAL_FORMS': '1', f'{names}-INITIAL_FORMS': '0',
            f'{names}-0-name': 'Some Creator',
            f'{names}-0-sort_name': 'Creator, Some',
            f'{names}-0-is_official_name': 'on',
            f'{names}-0-in_script': Script.LATIN_PK,
            f'{links}-TOTAL_FORMS': '0', f'{links}-INITIAL_FORMS': '0',
            'comments': ''}
    data.update({f'portrait_source_{key}': value
                 for key, value in portrait_source.items()})
    return client.post(reverse('add_creator'), data)


@pytest.mark.django_db
def test_portrait_source_fields_follow_the_notes(creator_client):
    """The two fields come after the notes, before the comments."""
    page = creator_client.get(reverse('add_creator')).content.decode()

    assert 'Portrait source description' in page
    assert 'Portrait source type' in page
    places = [page.find(f'id="id_{field}"') for field in [
      'notes', 'portrait_source_description', 'portrait_source_type',
      'comments']]
    assert -1 not in places and places == sorted(places)


@pytest.mark.django_db
def test_portrait_source_is_saved_with_the_change(creator_client,
                                                  source_type):
    """The source is saved as a data source of the field 'portrait'."""
    response = _add_creator(creator_client, type=source_type.id,
                            description='Photo by the publisher')

    assert response.status_code == 302
    revision = CreatorRevision.objects.get()
    source = revision.changeset.datasourcerevisions.get()
    assert source.field == 'portrait'
    assert source.source_type == source_type
    assert source.source_description == 'Photo by the publisher'


@pytest.mark.django_db
def test_portrait_source_type_needs_a_description(creator_client,
                                                  source_type):
    """A type without a description is refused, as for the biography."""
    response = _add_creator(creator_client, type=source_type.id)

    assert response.status_code == 200
    errors = response.context['form'].errors
    assert errors['portrait_source_description'] == [BOTH_SET]
    assert not CreatorRevision.objects.exists()


@pytest.mark.django_db
def test_compare_shows_the_portrait_source(creator_client, source_type):
    """The comparison of the change shows the source after the notes."""
    assert _add_creator(creator_client).status_code == 302
    revision = CreatorRevision.objects.get()
    DataSourceRevision.objects.create(
      changeset=revision.changeset, sourced_revision=revision,
      field='portrait', source_type=source_type,
      source_description='Photo by the publisher')

    page = creator_client.get(reverse('compare', kwargs={
      'id': revision.changeset.id})).content.decode()

    notes = page.find('> Notes </td>')
    assert -1 < notes < page.find('Photo by the publisher')
