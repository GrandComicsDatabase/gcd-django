import pytest

from apps.gcd.models import Character, Group


@pytest.mark.parametrize(
    ('model', 'index_name', 'fields'),
    [
        (
            Character,
            'gcd_character_v2_browse_idx',
            [
                'deleted',
                'sort_name',
                'year_first_published',
                'disambiguation',
                'id',
            ],
        ),
        (
            Character,
            'gcd_char_v2_lang_browse_idx',
            [
                'deleted',
                'language',
                'sort_name',
                'year_first_published',
                'disambiguation',
                'id',
            ],
        ),
        (
            Group,
            'gcd_group_v2_browse_idx',
            [
                'deleted',
                'sort_name',
                'year_first_published',
                'disambiguation',
                'id',
            ],
        ),
    ],
)
def test_character_group_models_expose_api_v2_browse_indexes(
    model,
    index_name,
    fields,
):
    index_map = {
        index.name: list(index.fields)
        for index in model._meta.indexes
    }

    assert index_map[index_name] == fields
