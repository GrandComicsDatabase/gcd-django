"""The issue of a collection item can be changed to another variant."""
import pytest
from django.contrib.auth.models import User

from apps.gcd.models import Issue, Publisher, Series
from apps.mycomics.forms import CollectionItemForm
from apps.mycomics.models import Collection, CollectionItem, Collector, \
                                 ConditionGradeScale
from apps.stddata.models import Country, Language


@pytest.fixture
def issues(db):
    """A base issue, an active and a deleted variant, and another issue."""
    country = Country.objects.get_or_create(
      id=929, defaults={'code': 'm9', 'name': 'Testland M'})[0]
    language = Language.objects.get_or_create(
      id=929, defaults={'code': 'm9', 'name': 'Testish M'})[0]
    publisher = Publisher.objects.create(
      name='Some Publisher', country=country, year_began=1990)
    series = Series.objects.create(
      name='Some Series', sort_name='Some Series', year_began=1990,
      country=country, language=language, publisher=publisher,
      is_comics_publication=True, publication_dates='1990')

    def issue(sort_code, number='1', **kwargs):
        return Issue.objects.create(
          number=number, series=series, sort_code=sort_code,
          publication_date='1990', key_date='1990-01-00', **kwargs)

    base = issue(1)
    return {'base': base,
            'variant': issue(2, variant_of=base, variant_name='Newsstand'),
            'deleted': issue(3, variant_of=base, variant_name='Recalled',
                             deleted=True),
            'other': issue(4, number='2')}


@pytest.fixture
def item(issues):
    collector = Collector.objects.create(
      user=User.objects.create_user('some.collector'),
      grade_system=ConditionGradeScale.objects.create(name='Some Scale'),
      default_language=issues['base'].series.language)
    collection = Collection.objects.create(
      collector=collector, name='Some Collection', own_used=True)
    item = CollectionItem.objects.create(
      issue=issues['base'], notes='Some notes', own=False)
    item.collections.add(collection)
    return item


def _form(item, data=None):
    return CollectionItemForm(item.collections.get().collector, data,
                              instance=item)


@pytest.mark.parametrize('current, choices', [
    ('base', ['base', 'variant']),
    ('variant', ['base', 'variant']),
    ('deleted', ['base', 'variant', 'deleted'])])
def test_item_offers_the_base_issue_and_its_variants(issues, item, current,
                                                     choices):
    item.issue = issues[current]
    field = _form(item).fields['issue']
    assert list(field.queryset) == [issues[name] for name in choices]
    assert field.empty_label is None


def test_item_of_an_issue_without_variants_has_no_issue_field(issues, item):
    item.issue = issues['other']
    assert 'issue' not in _form(item).fields


def test_item_refuses_an_issue_that_is_not_a_variant(issues, item):
    form = _form(item, {'issue': issues['other'].id, 'notes': 'Some notes',
                        'own': 'False'})
    assert not form.is_valid()
    assert list(form.errors) == ['issue']


def test_item_saved_as_a_variant_keeps_its_other_data(issues, item):
    form = _form(item, {'issue': issues['variant'].id, 'notes': 'Some notes',
                        'own': 'False'})
    assert form.is_valid(), form.errors
    form.save()
    item.refresh_from_db()
    assert item.issue == issues['variant']
    assert (item.notes, item.own) == ('Some notes', False)
    assert [c.name for c in item.collections.all()] == ['Some Collection']
