import pytest

from apps.gcd.models import Character, Group


@pytest.mark.parametrize(
    ('model', 'index_name'),
    [
        (Character, 'gcd_character_v2_browse_idx'),
        (Group, 'gcd_group_v2_browse_idx'),
    ],
)
def test_character_group_models_expose_api_v2_browse_indexes(
    model,
    index_name,
):
    index_map = {
        index.name: list(index.fields)
        for index in model._meta.indexes
    }

    assert index_map[index_name] == [
        'deleted',
        'sort_name',
        'year_first_published',
        'disambiguation',
        'id',
    ]
