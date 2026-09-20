import pytest

from scripts.check_dev_environment import (
    _require_at_least,
    _require_in_range,
)


@pytest.mark.parametrize('version', [(3, 13, 0), (3, 13, 6), (3, 13, 99)])
def test_python_313_release_line_is_supported(version):
    _require_in_range(version, (3, 13), (3, 14), 'Python')


@pytest.mark.parametrize('version', [(3, 12, 10), (3, 14, 0)])
def test_python_outside_313_release_line_is_rejected(version):
    with pytest.raises(RuntimeError, match='Python version mismatch'):
        _require_in_range(version, (3, 13), (3, 14), 'Python')


@pytest.mark.parametrize('version', [(8, 0, 0), (8, 4, 10), (9, 0, 0)])
def test_mysql_80_or_newer_is_supported(version):
    _require_at_least(version, (8, 0), 'MySQL')


def test_mysql_older_than_80_is_rejected():
    with pytest.raises(RuntimeError, match='MySQL version mismatch'):
        _require_at_least((5, 7, 44), (8, 0), 'MySQL')
