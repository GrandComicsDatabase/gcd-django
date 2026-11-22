import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gcd.models import (
  Cover, Creator, CreatorNameDetail, CreditType, Image, Issue, Publisher,
  Series, Story, StoryCredit)
from apps.gcd.models.story import CREDIT_TYPES, STORY_TYPES
from apps.stddata.models import Country, Language, Script


def _series(issue_count):
    country = Country.objects.get(code='us')
    publisher = Publisher.objects.create(name='Some Publisher',
                                         country=country)
    series = Series.objects.create(
      name='Some Series', publisher=publisher, country=country,
      language=Language.objects.get(code='en'), year_began=2020)
    Issue.objects.bulk_create(Issue(series=series, number=str(number),
                                    sort_code=number)
                              for number in range(1, issue_count + 1))
    return series


def _story(issue, number, type_name, pages, **fields):
    return Story(issue=issue, sequence_number=number,
                 type_id=STORY_TYPES[type_name], page_count=pages, **fields)


def _creator_name():
    script = Script.objects.get_or_create(
      id=Script.LATIN_PK, defaults={'code': 'Latn', 'name': 'Latin',
                                    'number': Script.LATIN_PK})[0]
    creator = Creator.objects.create(gcd_official_name='Some Creator',
                                     sort_name='Some Creator')
    return CreatorNameDetail.objects.create(name='Some Creator',
                                            creator=creator, in_script=script)


def _status_page(client, series):
    return client.get(reverse('series_index_status',
                              kwargs={'series_id': series.id}))


@pytest.mark.django_db
def test_index_status_shows_the_indexing_state_of_each_issue(client):
    series = _series(2)
    first = series.active_issues().get(number='1')
    Issue.objects.filter(id=first.id).update(page_count=32,
                                             page_count_uncertain=True)
    Story.objects.bulk_create([
      _story(first, 0, 'cover', 1, pencils='?'),
      _story(first, 1, 'comic story', 20, script='?', pencils='? (signed)'),
      _story(first, 2, 'ad', 2),
      _story(first, 3, 'comic story', 5, script='Some Writer'),
      _story(first, 4, 'comic story', 10, script='?', deleted=True)])
    Cover.objects.create(issue=first)
    Image.objects.create(object=first, type_id=1)
    Image.objects.create(object=first, type_id=2, deleted=True)
    # migrated credits: only the uncertain one of a sequence counts as "?"
    story, deleted_story = Story.objects.filter(
      issue=first, sequence_number__in=(3, 4))
    pencils = CreditType.objects.get_or_create(
      id=CREDIT_TYPES['pencils'], defaults={'name': 'pencils',
                                         'sort_code': 2})[0]
    name = _creator_name()
    StoryCredit.objects.bulk_create(
      StoryCredit(story=on_story, creator=name, credit_type=pencils,
                  uncertain=uncertain, deleted=deleted)
      for on_story, uncertain, deleted in ((story, True, False),
                                           (story, False, False),
                                           (story, True, True),
                                           (deleted_story, True, False)))

    response = _status_page(client, series)

    assert response.status_code == 200
    assert list(response.context['table'].as_values()) == [
      ['Issue', 'Total Pages', 'Indexed Pages', 'Comic Pages', 'Ad Pages',
       '"?" Credits', 'Cover Sequence', 'Cover Scan', 'Other Scans'],
      ['1', '32 ?', '28', '25', '2', 4, 'True', 'True', 'indicia scan'],
      ['2', '', '0', '0', '0', 0, 'False', 'False', None]]
    assert '<span class="true">Yes</span>' in response.content.decode()


@pytest.mark.django_db
def test_series_page_links_to_the_index_status(client):
    series = _series(1)

    response = client.get(reverse('show_series',
                                  kwargs={'series_id': series.id}))

    assert 'href="%s"' % reverse('series_index_status',
                                 kwargs={'series_id': series.id}) \
        in response.content.decode()


@pytest.mark.django_db
def test_index_status_needs_no_query_per_issue(client):
    small, large = _series(1), _series(300)
    issues = list(Issue.objects.all())
    Story.objects.bulk_create(_story(issue, 0, 'cover', 1, pencils='?')
                              for issue in issues)
    Cover.objects.bulk_create(Cover(issue=issue) for issue in issues)
    Image.objects.bulk_create(Image(object=issue, type_id=1)
                              for issue in issues)
    _status_page(client, small)

    with CaptureQueriesContext(connection) as small_queries:
        _status_page(client, small)
    with CaptureQueriesContext(connection) as large_queries:
        response = _status_page(client, large)

    assert len(response.context['table'].page.object_list) == 300
    assert len(large_queries) == len(small_queries)
