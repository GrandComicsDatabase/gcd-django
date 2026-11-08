import pytest

from apps.oi.models import SeriesRevision
from apps.oi.templatetags.compare import field_value


@pytest.mark.parametrize('field', ['has_about_comics',
                                   'has_publisher_code_number'])
@pytest.mark.parametrize('value, expected', [(True, 'Yes'), (False, 'No')])
def test_series_flags_show_yes_no(field, value, expected):
    revision = SeriesRevision(**{field: value})
    assert field_value(revision, field) == expected
