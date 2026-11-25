import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Issue, Story
from apps.oi.import_export import BRAND, ISSUE_PAGE_COUNT, ON_SALE_DATE, \
                                  STORY_PAGE_COUNT


@pytest.fixture
def logged_in(client, any_indexer):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)


def _exported_lines(client, issue_id):
    response = client.get(reverse('export_issue',
                                  kwargs={'issue_id': issue_id}))
    assert response.status_code == 200
    return [line.split('\t')
            for line in response.content.decode().split('\r\n') if line]


@pytest.mark.django_db
def test_export_says_none_for_an_issue_without_a_brand(client, logged_in,
                                                       any_added_issue):
    any_added_issue.brand_emblem.clear()
    Issue.objects.filter(pk=any_added_issue.pk).update(no_brand=True)

    assert _exported_lines(client, any_added_issue.id)[0][BRAND] == 'None'


@pytest.mark.django_db
def test_export_gives_the_names_of_the_brands(client, logged_in,
                                              any_added_issue):
    brand = any_added_issue.brand_emblem.get()

    assert _exported_lines(client, any_added_issue.id)[0][BRAND] == brand.name


@pytest.mark.django_db
def test_export_marks_an_uncertain_issue_page_count(client, logged_in,
                                                    any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      page_count=64, page_count_uncertain=True)

    assert _exported_lines(
      client, any_added_issue.id)[0][ISSUE_PAGE_COUNT].endswith('?')


@pytest.mark.django_db
def test_export_leaves_a_certain_issue_page_count_alone(client, logged_in,
                                                        any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      page_count=64, page_count_uncertain=False)

    assert not _exported_lines(
      client, any_added_issue.id)[0][ISSUE_PAGE_COUNT].endswith('?')


@pytest.mark.django_db
def test_export_marks_an_uncertain_on_sale_date(client, logged_in,
                                                any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      on_sale_date='1946-11-23', on_sale_date_uncertain=True)

    assert _exported_lines(
      client, any_added_issue.id)[0][ON_SALE_DATE] == '1946-11-23?'


@pytest.mark.django_db
def test_export_adds_no_question_mark_to_a_missing_on_sale_date(
  client, logged_in, any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      on_sale_date='', on_sale_date_uncertain=True)

    assert _exported_lines(client, any_added_issue.id)[0][ON_SALE_DATE] == ''


@pytest.mark.django_db
def test_export_marks_an_uncertain_sequence_page_count(client, logged_in,
                                                       any_added_story):
    Story.objects.filter(pk=any_added_story.pk).update(
      page_count=8, page_count_uncertain=True)

    lines = _exported_lines(client, any_added_story.issue_id)
    assert lines[1][STORY_PAGE_COUNT].endswith('?')
