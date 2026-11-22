"""The table of contents of an issue says how many pages are indexed."""

import re
from decimal import Decimal

import pytest

from django.core.management import call_command
from django.urls import reverse

from apps.gcd.models import Issue, Story, StoryType


@pytest.fixture
def variant(db):
    """
    The seeded variant, without sequences or a page count of its own. Its
    base has 36 pages, a cover sequence of 1 page and a story of 29.5 pages.
    """
    call_command('seed_development_data')
    variant = Issue.objects.get(variant_of__isnull=False)
    base = variant.variant_of
    Issue.objects.filter(id=base.id).update(page_count=36)
    Story.objects.filter(issue=base, sequence_number=0).update(
      type=StoryType.objects.get(name='cover'), page_count=1)
    Story.objects.create(issue=base, sequence_number=1, page_count=Decimal(
      '29.5'), type=StoryType.objects.get(name='comic story'))
    return variant


def _table_of_contents(client, issue):
    response = client.get(reverse('show_issue',
                                  kwargs={'issue_id': issue.id}))
    assert response.status_code == 200
    page = re.sub(r'\s+', ' ', response.content.decode())
    return page[page.index('class="toc '):]


@pytest.mark.parametrize('issue_pages, shown', [
  ({'page_count': 36}, '30.5 of 36'),
  ({'page_count': None}, '30.5'),
  ({'page_count_uncertain': True}, '30.5 of 36 ?')])
def test_indexed_pages_count_the_cover_and_show_the_issue_pages(
      client, variant, issue_pages, shown):
    Issue.objects.filter(id=variant.variant_of_id).update(**issue_pages)

    toc = _table_of_contents(client, variant.variant_of)

    assert 'Pages indexed:</span> %s</div>' % shown in toc


def test_indexed_pages_of_a_variant_leave_out_the_base_cover(client,
                                                             variant):
    toc = _table_of_contents(client, variant)

    assert 'Pages indexed:</span> 29.5</div>' in toc


def test_a_variant_counts_its_own_cover_sequence(client, variant):
    Story.objects.create(issue=variant, sequence_number=0, page_count=2,
                         type=StoryType.objects.get(name='cover'))

    toc = _table_of_contents(client, variant)

    assert 'Pages indexed:</span> 31.5</div>' in toc


def test_no_indexed_pages_without_sequences(client, variant):
    Story.objects.filter(issue=variant.variant_of).update(deleted=True)

    assert 'Pages indexed:' not in _table_of_contents(client,
                                                      variant.variant_of)
