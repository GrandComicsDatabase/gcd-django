"""The language box of the group relation form and its Group B list.

Group B of the page that adds a relation to a group lists the groups whose
name holds the typed text, in all languages. The language box above it
narrows the list to one language; left empty, the list stays as it was.
"""
import json

import pytest
from django.urls import reverse

from apps.gcd.models import Group
from apps.oi.forms.character import GroupRelationRevisionForm
from apps.stddata.models import Language

NAME = 'Test Team'

pytestmark = pytest.mark.django_db


@pytest.fixture
def groups(db):
    """Groups of the same name: two English, two German, one Italian."""
    languages = {code: Language.objects.get_or_create(
                   code=code, defaults={'name': name})[0]
                 for code, name in [('en', 'English'), ('de', 'German'),
                                    ('it', 'Italian'), ('fi', 'Finnish')]}
    return [Group.objects.create(
              name=NAME, sort_name=NAME, disambiguation=str(number),
              description='', notes='', year_first_published=1960 + number,
              language=languages[code])
            for number, code in enumerate(['en', 'de', 'en', 'de', 'it'])]


def _list(client, forwarded):
    """Return the ids that Group B lists for the name, in all pages."""
    found, page, more = [], 1, True
    while more:
        data = client.get(reverse('group_autocomplete'),
                          {'q': NAME, 'page': page,
                           'forward': json.dumps(forwarded)}).json()
        found += [int(result['id']) for result in data['results']]
        more = data['pagination']['more']
        page += 1
    return found


def _ids(groups, codes):
    """Return the sorted ids of the groups of the given languages."""
    return sorted(group.id for group in groups
                  if group.language.code in codes)


def test_chosen_language_lists_only_its_groups(client, any_indexer, groups):
    """With Italian chosen, Group B lists only the Italian group."""
    client.force_login(any_indexer)

    assert sorted(_list(client, {'language': 'it'})) == _ids(groups, ['it'])


def test_chosen_language_with_the_relation_filter(client, any_indexer,
                                                  groups):
    """The choice narrows the list that the relation type already narrows.

    For "republished as" from an English group, the list holds the other
    languages; with German chosen it holds the German ones only.
    """
    client.force_login(any_indexer)
    relation = {'language_code': 'en', 'relation_type': '1'}

    assert sorted(_list(client, relation)) == _ids(groups, ['de', 'it'])
    assert sorted(_list(client, dict(relation, language='de'))) == \
        _ids(groups, ['de'])


def test_no_language_lists_all_languages(client, any_indexer, groups):
    """With no language chosen, the groups of all languages are listed."""
    client.force_login(any_indexer)

    assert sorted(_list(client, {'language': ''})) == \
        _ids(groups, ['en', 'de', 'it'])


def test_language_box_offers_the_languages_of_groups(groups):
    """The box offers all languages first, then those that have groups.

    It sits above Group B and is passed to its list.
    """
    form = GroupRelationRevisionForm()
    field = form.fields['to_group_language']
    forwarded = [(item.src, item.dst)
                 for item in form.fields['to_group'].widget.forward
                 if not isinstance(item, str)]

    assert [(str(value), label) for value, label in field.choices] == [
      ('', 'All languages'), ('en', 'English'), ('de', 'German'),
      ('it', 'Italian')]
    assert not field.required
    assert list(form.fields).index('to_group_language') == \
        list(form.fields).index('to_group') - 1
    assert forwarded == [('to_group_language', 'language')]
