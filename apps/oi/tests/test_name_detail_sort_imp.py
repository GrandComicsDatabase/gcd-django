"""
The IMP of a sort name equal to the name, for the names of characters
and groups, as for the names of creators.
"""
import pytest

from apps.oi.models import (
    CharacterNameDetailRevision, GroupNameDetailRevision)


@pytest.mark.parametrize('revision_class', [CharacterNameDetailRevision,
                                            GroupNameDetailRevision])
@pytest.mark.parametrize('added, imps', [(True, 0), (False, 1)])
def test_sort_name_equal_to_name_scores_only_for_existing_names(
      revision_class, added, imps):
    """
    A new name gets no IMP for a sort name equal to the name; correcting
    the sort name of an existing name to the name gets one.
    """
    previous = None if added else revision_class()
    revision = revision_class(name='Test Name', sort_name='Test Name',
                              previous_revision=previous)

    assert revision._imps_for('sort_name') == imps
