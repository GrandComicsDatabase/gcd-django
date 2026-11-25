import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.gcd.models import Issue, Story
from apps.oi.interchange import YES, parse_items


@pytest.fixture
def logged_in(client, any_indexer):
    any_indexer.user_permissions.add(Permission.objects.get(
      codename='can_reserve', content_type__app_label='indexer'))
    client.force_login(any_indexer)


def _exported_lines(client, issue_id):
    """
    The issue and its sequences of the downloaded TSV file, by column name.
    """
    response = client.get(reverse('export_issue',
                                  kwargs={'issue_id': issue_id}))
    assert response.status_code == 200
    lines = [line.split('\t')
             for line in response.content.decode().split('\r\n') if line]
    return [dict(zip(lines[0], line)) for line in lines[1:]]


@pytest.mark.django_db
def test_export_says_none_for_an_issue_without_a_brand(client, logged_in,
                                                       any_added_issue):
    any_added_issue.brand_emblem.clear()
    Issue.objects.filter(pk=any_added_issue.pk).update(no_brand=True)

    assert _exported_lines(client, any_added_issue.id)[0]['no_brand'] == YES


@pytest.mark.django_db
def test_export_gives_the_names_of_the_brands(client, logged_in,
                                              any_added_issue):
    brand = any_added_issue.brand_emblem.get()

    cell = _exported_lines(client, any_added_issue.id)[0]['brand_emblem']
    # a name is written in the notation, which keeps its spaces
    assert [item.name.label for item in parse_items(cell)] == [brand.name]


@pytest.mark.django_db
def test_export_marks_an_uncertain_issue_page_count(client, logged_in,
                                                    any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      page_count=64, page_count_uncertain=True)

    assert _exported_lines(
      client, any_added_issue.id)[0]['page_count_uncertain'] == YES


@pytest.mark.django_db
def test_export_leaves_a_certain_issue_page_count_alone(client, logged_in,
                                                        any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      page_count=64, page_count_uncertain=False)

    assert _exported_lines(
      client, any_added_issue.id)[0].get('page_count_uncertain', '') == ''


@pytest.mark.django_db
def test_export_marks_an_uncertain_on_sale_date(client, logged_in,
                                                any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      on_sale_date='1946-11-23', on_sale_date_uncertain=True)

    issue_line = _exported_lines(client, any_added_issue.id)[0]
    assert issue_line['on_sale_date'] == '1946-11-23'
    assert issue_line['on_sale_date_uncertain'] == YES


@pytest.mark.django_db
def test_export_adds_no_question_mark_to_a_missing_on_sale_date(
  client, logged_in, any_added_issue):
    Issue.objects.filter(pk=any_added_issue.pk).update(
      on_sale_date='', on_sale_date_uncertain=True)

    assert _exported_lines(
      client, any_added_issue.id)[0].get('on_sale_date', '') == ''


@pytest.mark.django_db
def test_export_marks_an_uncertain_sequence_page_count(client, logged_in,
                                                       any_added_story):
    Story.objects.filter(pk=any_added_story.pk).update(
      page_count=8, page_count_uncertain=True)

    lines = _exported_lines(client, any_added_story.issue_id)
    assert lines[1]['page_count_uncertain'] == YES
