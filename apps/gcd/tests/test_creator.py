# -*- coding: utf-8 -*-

from types import SimpleNamespace

import mock

from apps.gcd.models.creator import (
    Creator, CreatorNameDetail, NAME_TYPES, NameType)


def _house_name_credit(matching_name):
    creator = Creator(gcd_official_name='Credited Creator',
                      disambiguation='')
    house_name = CreatorNameDetail(
        name='House Alias',
        creator=creator,
        type=NameType(id=NAME_TYPES['house']),
        is_official_name=False)
    credit = SimpleNamespace(
        is_credited=True,
        credited_as='',
        uncertain=False,
        creator=house_name,
        is_sourced=False,
        credit_name='')

    active_names = mock.MagicMock()
    target_creator = mock.MagicMock()
    official_name = SimpleNamespace(
        name='Official House Name', creator=target_creator)
    active_names.get.return_value = official_name
    active_names.filter.return_value.first.return_value = matching_name
    active_names.filter.return_value.__bool__.return_value = \
        matching_name is not None
    target_creator.active_names.return_value = active_names

    relation_manager = mock.MagicMock()
    relation_manager.filter.return_value.exists.return_value = True
    relation_manager.get.return_value.to_creator = target_creator

    return house_name, credit, relation_manager, active_names


def test_display_credit_queries_matching_house_name_once():
    matching_name = SimpleNamespace(name='House Alias')
    house_name, credit, relation_manager, active_names = \
        _house_name_credit(matching_name)

    with mock.patch.object(
      CreatorNameDetail, 'creator_relation',
      new_callable=mock.PropertyMock, return_value=relation_manager):
        credit_text = house_name.display_credit(credit, url=False)

    assert credit_text == \
        'Credited Creator (under house name House Alias)'
    active_names.filter.assert_called_once_with(name='House Alias')


def test_display_credit_keeps_official_house_name_without_match():
    house_name, credit, relation_manager, active_names = \
        _house_name_credit(None)

    with mock.patch.object(
      CreatorNameDetail, 'creator_relation',
      new_callable=mock.PropertyMock, return_value=relation_manager):
        credit_text = house_name.display_credit(credit, url=False)

    assert credit_text == \
        'Credited Creator (under house name Official House Name)'
    active_names.filter.assert_called_once_with(name='House Alias')
