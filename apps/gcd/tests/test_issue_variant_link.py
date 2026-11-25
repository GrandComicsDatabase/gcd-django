"""The page of a My Comics item names the variant it holds."""

import pytest

from django.core.management import call_command
from django.template import Context, Template

from apps.gcd.models import Issue


@pytest.fixture
def variant(db):
    """The seeded "Direct Market Variant" of issue #1."""
    call_command('seed_development_data')
    return Issue.objects.get(variant_of__isnull=False)


def test_the_link_names_the_variant(variant):
    link = variant.full_name_with_variant_link

    assert link == '%s <a href="%s">#1 [Direct Market Variant]</a>' % (
      variant.series.full_name_with_link(), variant.get_absolute_url())


def test_the_link_of_a_base_issue_is_the_usual_link(variant):
    base = variant.variant_of

    assert base.full_name_with_variant_link == base.full_name_with_link()


def test_the_link_is_not_escaped_in_a_template(variant):
    shown = Template('<h1>{{ issue.full_name_with_variant_link }}</h1>')\
      .render(Context({'issue': variant}))

    assert '<a href="%s">#1 [Direct Market Variant]</a></h1>' % (
      variant.get_absolute_url()) in shown
