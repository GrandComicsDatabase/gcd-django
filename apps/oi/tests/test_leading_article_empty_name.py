# -*- coding: utf-8 -*-
"""
A name of one word that ends with an apostrophe has nothing after the
would-be article: it has no leading article, and its sort name is the
name itself, never an empty text.
"""

import pytest

from apps.gcd.models import (
    Feature, FeatureLogo, FeatureNameDetail, Series, StoryArc)
from apps.oi.forms.series import SeriesRevisionForm
from apps.oi.forms.story import StoryArcRevisionForm
from apps.oi.models import (
    FeatureLogoRevision, FeatureNameDetailRevision, FeatureRevision,
    SeriesRevision, StoryArcRevision, remove_leading_article)
from apps.oi.templatetags.compare import field_value
from apps.oi.tests.test_year_order import _form_data

# Each revision with a leading article box, the name of its link to the
# record and the record that keeps the sort name.
REVISIONS = (
    (SeriesRevision, 'series', Series),
    (StoryArcRevision, 'story_arc', StoryArc),
    (FeatureRevision, 'feature', Feature),
    (FeatureLogoRevision, 'feature_logo', FeatureLogo),
    (FeatureNameDetailRevision, 'feature_name_detail', FeatureNameDetail),
)


@pytest.mark.parametrize('name, without_article', (
    ('The Alpha Press', 'Alpha Press'),
    ('The  Alpha Press', 'Alpha Press'),
    ("L'Uomo", 'Uomo'),
    ('Alpha', 'Alpha'),
))
def test_the_leading_article_of_a_name_is_removed(name, without_article):
    assert remove_leading_article(name) == without_article


@pytest.mark.parametrize('name', ("Alpha'", "'Alpha'", "L'"))
def test_a_name_with_nothing_after_the_article_comes_back_whole(name):
    assert remove_leading_article(name) == name


@pytest.mark.parametrize('revision_class, link, record_class', REVISIONS)
@pytest.mark.parametrize('name, sort_name', (
    ('The Alpha Press', 'Alpha Press'),
    ("L'Uomo", 'Uomo'),
    ("Alpha'", "Alpha'"),
))
def test_the_sort_name_of_a_change_is_never_empty(
        revision_class, link, record_class, name, sort_name):
    record = record_class(name=name)
    revision = revision_class(leading_article=True, name=name,
                              **{link: record})

    revision._post_assign_fields({})

    assert record.sort_name == sort_name


@pytest.mark.parametrize('name, shown', (
    ('The Alpha Press', 'Yes (sorted as: Alpha Press)'),
    ("Alpha'", "Yes (sorted as: Alpha')"),
))
def test_the_compare_page_shows_the_name_it_is_sorted_as(name, shown):
    revision = SeriesRevision(leading_article=True, name=name)

    assert field_value(revision, 'leading_article') == shown


@pytest.mark.django_db
def test_the_series_form_refuses_the_box_when_nothing_follows(
        series_add_values):
    values = dict(series_add_values, is_current=False, leading_article=True)

    with_article = SeriesRevisionForm(_form_data(values, name="L'Uomo"))
    assert with_article.is_valid(), with_article.errors

    only_article = SeriesRevisionForm(_form_data(values, name="Alpha'"))
    assert not only_article.is_valid()
    assert only_article.errors == {'__all__': [
      'The series name is only one word, you cannot specify '
      'a leading article in this case.']}


@pytest.mark.django_db
def test_the_story_arc_form_refuses_the_box_when_nothing_follows(
        any_language):
    values = {'leading_article': True, 'language': any_language}

    with_article = StoryArcRevisionForm(_form_data(values, name="L'Uomo"))
    assert with_article.is_valid(), with_article.errors

    only_article = StoryArcRevisionForm(_form_data(values, name="Alpha'"))
    assert not only_article.is_valid()
    assert only_article.errors == {'__all__': [
      'The name is only one word, you cannot specify '
      'a leading article in this case.']}
