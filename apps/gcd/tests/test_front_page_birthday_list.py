"""The front page timeline of creators is computed once for each date."""

from datetime import datetime

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.gcd.models import (
    Creator, CreatorNameDetail, CreditType, Issue, Publisher, Series,
    Story, StoryCredit, StoryType,
)
from apps.gcd.views import index
from apps.stddata.models import Country, Date, Language, Script


def set_today(monkeypatch, year, month, day):
    """Make the front page view take the given date as today."""

    class FixedDate(datetime):
        """A datetime whose today() is the given date."""

        @classmethod
        def today(cls):
            """Return noon of the given date."""
            return cls(year, month, day, 12)

    monkeypatch.setattr('apps.gcd.views.datetime', FixedDate)


def creator_queries(queries):
    """Return the captured queries that read the creator tables."""
    return [query for query in queries if 'gcd_creator' in query['sql']]


@pytest.fixture
def front_page(settings, monkeypatch):
    """Return a function giving the creators the front page would show."""
    settings.USE_TEMPLATESADMIN = True
    monkeypatch.setattr('apps.gcd.views.render',
                        lambda request, template, context: context)
    cache.clear()

    def creators():
        """Run the front page view and return its list of creators."""
        request = RequestFactory().get('/')
        request.LANGUAGE_CODE = 'en'
        return index(request)['creators']

    yield creators
    cache.clear()


@pytest.fixture
def make_creator(db):
    """Return a function adding a creator credited in eleven issues."""
    country, _ = Country.objects.get_or_create(
        code='zz', defaults={'name': 'Test Country'})
    language, _ = Language.objects.get_or_create(
        code='zz', defaults={'name': 'Test Language'})
    script, _ = Script.objects.get_or_create(
        id=Script.LATIN_PK,
        defaults={'code': 'Latn', 'number': Script.LATIN_PK, 'name': 'Latin'})
    story_type, _ = StoryType.objects.get_or_create(
        name='birthday-test', defaults={'sort_code': 99060})
    credit_type, _ = CreditType.objects.get_or_create(
        name='birthday-test', defaults={'sort_code': 99060})
    publisher = Publisher.objects.create(
        name='Test Publisher', country=country, year_began=1991)
    series = Series.objects.create(
        name='Test Series', sort_name='Test Series', publisher=publisher,
        country=country, language=language, year_began=1991)
    stories = []
    for number in range(11):
        issue = Issue.objects.create(series=series, number=str(number),
                                     sort_code=number)
        stories.append(Story.objects.create(issue=issue, type=story_type,
                                            sequence_number=0))

    def make(name, month, day):
        """Add a creator born on the given day, with a biography."""
        creator = Creator.objects.create(
            gcd_official_name=name, sort_name=name, bio='Test biography',
            birth_date=Date.objects.create(year='1970', month=month,
                                           day=day))
        creator_name = CreatorNameDetail.objects.create(
            name=name, creator=creator, in_script=script)
        for story in stories:
            StoryCredit.objects.create(story=story, creator=creator_name,
                                       credit_type=credit_type)
        return creator

    return make


def test_second_call_runs_no_creator_query(
        front_page, make_creator, monkeypatch):
    creator = make_creator('Some Creator', '11', '28')
    set_today(monkeypatch, 2026, 11, 28)
    first = front_page()

    with CaptureQueriesContext(connection) as queries:
        second = front_page()
        birthdays = [shown.display_birthday() for shown in second]

    assert creator_queries(queries) == []
    # The birth dates come with the list, as before.
    assert len(queries) == 0
    assert [shown.pk for shown in first] == [creator.pk]
    assert [(shown.pk, shown.issue_count) for shown in second] == \
        [(shown.pk, shown.issue_count) for shown in first]
    assert birthdays == [shown.display_birthday() for shown in first]


def test_next_date_gets_its_own_list(front_page, make_creator, monkeypatch):
    earlier = make_creator('Some Creator', '11', '28')
    later = make_creator('Other Creator', '11', '29')
    set_today(monkeypatch, 2026, 11, 28)
    assert [shown.pk for shown in front_page()] == [earlier.pk]

    set_today(monkeypatch, 2026, 11, 29)
    with CaptureQueriesContext(connection) as queries:
        creators = front_page()

    assert creator_queries(queries)
    assert [shown.pk for shown in creators] == [later.pk, earlier.pk]


def test_list_ends_at_the_first_new_birthday_after_the_tenth(
        front_page, make_creator, monkeypatch):
    # One creator a day from November 28 back to 19, a second one on the
    # 19th, the day of the tenth, and one on the 18th.
    days = [str(day) for day in range(28, 18, -1)] + ['19', '18']
    creators = [make_creator('Creator %02d' % number, '11', day)
                for number, day in enumerate(days)]
    set_today(monkeypatch, 2026, 11, 28)

    shown = front_page()

    assert [creator.pk for creator in shown] == \
        [creator.pk for creator in creators[:11]]
    assert {creator.issue_count for creator in shown} == {11}
