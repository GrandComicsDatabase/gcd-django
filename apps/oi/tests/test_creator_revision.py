import pytest

from apps.oi.models import CreatorNameDetailRevision


@pytest.mark.parametrize('added, imps', [(True, 0), (False, 1)])
def test_sort_name_equal_to_name_scores_only_for_existing_names(added,
                                                                imps):
    previous = None if added else CreatorNameDetailRevision()
    revision = CreatorNameDetailRevision(name='Tezuka Osamu',
                                         sort_name='Tezuka Osamu',
                                         previous_revision=previous)

    assert revision._imps_for('sort_name') == imps
