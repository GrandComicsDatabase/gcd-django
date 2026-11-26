# -*- coding: utf-8 -*-
"""
A publisher name can start with an article that sorting ignores, as a
series name can.  The API keeps its fields and its order by name.
"""

import importlib

import pytest
from django.apps import apps as django_apps
from django.urls import reverse

from apps.api.serializers import PublisherSerializer
from apps.gcd.models import Publisher
from apps.oi import states
from apps.oi.forms.publisher import PublisherRevisionForm
from apps.oi.models import PublisherRevision

# The fields of a publisher in the API before publishers had a sort name.
API_PUBLISHER_FIELDS = [
    'api_url', 'country', 'modified', 'name', 'year_began', 'year_ended',
    'year_began_uncertain', 'year_ended_uncertain', 'year_overall_began',
    'year_overall_ended', 'year_overall_began_uncertain',
    'year_overall_ended_uncertain', 'notes', 'url', 'brand_count',
    'indicia_publisher_count', 'series_count', 'issue_count']


def _add_publisher(changeset, country, name, leading_article=False):
    """Add a publisher through a revision committed as an approval does."""
    revision = PublisherRevision(changeset=changeset, name=name,
                                 country=country, year_began=1970)
    revision.leading_article = leading_article
    revision.save()
    revision.commit_to_display()
    return revision.publisher


@pytest.mark.django_db
def test_the_name_search_sorts_without_the_leading_article(
        client, any_adding_changeset, any_country):
    _add_publisher(any_adding_changeset, any_country, 'Beta Press')
    _add_publisher(any_adding_changeset, any_country, 'The Alpha Press',
                   leading_article=True)

    response = client.get(reverse('publisher_by_name',
                                  kwargs={'publisher_name': 'Press'}))

    assert response.status_code == 200
    page = response.content.decode()
    assert page.index('The Alpha Press') < page.index('Beta Press')


@pytest.mark.django_db
def test_the_box_sets_the_sort_name_and_comes_back_on_edit(
        any_adding_changeset, any_editing_changeset, any_country):
    publisher = _add_publisher(any_adding_changeset, any_country,
                               'The Alpha Press', leading_article=True)
    any_adding_changeset.state = states.APPROVED
    any_adding_changeset.save()
    assert publisher.name == 'The Alpha Press'
    assert publisher.sort_name == 'Alpha Press'

    revision = PublisherRevision.clone(data_object=publisher,
                                       changeset=any_editing_changeset)
    assert revision.leading_article is True
    revision.leading_article = False
    revision.save()
    revision.commit_to_display()

    publisher = Publisher.objects.get(pk=publisher.pk)
    assert publisher.sort_name == 'The Alpha Press'


@pytest.mark.django_db
def test_the_form_refuses_the_box_for_a_name_of_one_word(any_country):
    data = {'name': 'Alpha', 'leading_article': 'on',
            'country': any_country.id, 'url': '', 'notes': '',
            'keywords': '', 'comments': ''}
    form = PublisherRevisionForm(data=data)
    assert not form.is_valid()
    assert 'only one word' in str(form.non_field_errors())

    data['name'] = 'The Alpha Press'
    assert PublisherRevisionForm(data=data).is_valid()


@pytest.mark.django_db
def test_the_migration_sorts_each_publisher_by_its_name(any_country):
    publisher = Publisher.objects.create(name='The Alpha Press',
                                         country=any_country)
    migration = importlib.import_module(
        'apps.gcd.migrations.0072_publisher_sort_name')

    migration.fill_sort_name(django_apps, None)

    publisher.refresh_from_db()
    assert publisher.sort_name == 'The Alpha Press'


def test_the_api_serializer_keeps_its_fields():
    assert list(PublisherSerializer().fields) == API_PUBLISHER_FIELDS


@pytest.mark.django_db
def test_the_api_keeps_its_answer_and_its_order_by_name(
        client, any_adding_changeset, any_country):
    _add_publisher(any_adding_changeset, any_country, 'Beta Press')
    _add_publisher(any_adding_changeset, any_country, 'The Alpha Press',
                   leading_article=True)

    response = client.get('/api/publisher/', HTTP_ACCEPT='application/json')

    assert response.status_code == 200
    results = response.json()['results']
    names = [result['name'] for result in results]
    assert names == ['Beta Press', 'The Alpha Press']
    assert all(list(result) == API_PUBLISHER_FIELDS for result in results)
