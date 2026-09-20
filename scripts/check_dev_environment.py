"""Verify the supported development runtime contract."""

import os
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 13)
MAXIMUM_PYTHON = (3, 14)
EXPECTED_DJANGO = (5, 2)
MINIMUM_MYSQL = (8, 0)


def _require(actual, expected, component):
    """Raise a clear error when a runtime version does not match."""
    if actual != expected:
        raise RuntimeError(
            f'{component} version mismatch: expected {expected}, got {actual}'
        )


def _require_in_range(actual, minimum, maximum, component):
    """Require a version within a lower-inclusive, upper-exclusive range."""
    if not minimum <= actual < maximum:
        raise RuntimeError(
            f'{component} version mismatch: expected >= {minimum} and '
            f'< {maximum}, got {actual}'
        )


def _require_at_least(actual, minimum, component):
    """Require a version at or above a supported minimum."""
    if actual < minimum:
        raise RuntimeError(
            f'{component} version mismatch: expected >= {minimum}, '
            f'got {actual}'
        )


def main():
    """Check Python, Django, MySQL, and Django system configuration."""
    _require_in_range(
        sys.version_info[:3], MINIMUM_PYTHON, MAXIMUM_PYTHON, 'Python'
    )

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')

    import django
    from django.core.management import call_command
    from django.db import connection

    _require(django.VERSION[:2], EXPECTED_DJANGO, 'Django')

    django.setup()
    call_command('check')

    mysql_version = connection.get_database_version()
    _require_at_least(mysql_version, MINIMUM_MYSQL, 'MySQL')
    mysql_version_text = '.'.join(map(str, mysql_version))

    print(
        'Development environment verified: '
        f'Python {sys.version_info.major}.{sys.version_info.minor}.'
        f'{sys.version_info.micro}, Django {django.get_version()}, '
        f'MySQL {mysql_version_text}'
    )


if __name__ == '__main__':
    main()
