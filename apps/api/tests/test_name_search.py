# -*- coding: utf-8 -*-
from django.db.models.query import EmptyQuerySet

from apps.api.views import IssuesList, SeriesList, _has_non_bmp_characters


def _queryset(view_class, **kwargs):
    view = view_class()
    view.kwargs = kwargs
    return view.get_queryset()


def test_has_non_bmp_characters():
    assert _has_non_bmp_characters("don't yoga with imps\U0001f608")
    assert not _has_non_bmp_characters("Spider-Man")
    assert not _has_non_bmp_characters('Tim und Struppi äöü')


def test_series_name_with_emoji_returns_empty_without_query():
    # utf8mb3 columns cannot hold 4-byte characters; querying them raises
    # MySQL error 1267, so the view must not send the LIKE at all.
    qs = _queryset(SeriesList, name="don't yoga with imps\U0001f608")
    assert isinstance(qs, EmptyQuerySet)

    qs = _queryset(SeriesList, name='imps\U0001f608', year=2020)
    assert isinstance(qs, EmptyQuerySet)


def test_issue_search_with_emoji_returns_empty_without_query():
    qs = _queryset(IssuesList, name='imps\U0001f608', number='1')
    assert isinstance(qs, EmptyQuerySet)

    qs = _queryset(IssuesList, name='imps', number='1\U0001f608',
                   year='2020')
    assert isinstance(qs, EmptyQuerySet)


def test_plain_series_name_still_filters():
    qs = _queryset(SeriesList, name='Nathan Never')
    assert not isinstance(qs, EmptyQuerySet)
    assert 'LIKE' in str(qs.query)
