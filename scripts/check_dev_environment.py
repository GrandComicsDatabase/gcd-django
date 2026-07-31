"""Verify the provisional development runtime contract."""

import os
import sys
from pathlib import Path


EXPECTED_PYTHON = (3, 14, 6)
EXPECTED_DJANGO = (5, 2)
EXPECTED_MYSQL = '8.4.10'


def _require(actual, expected, component):
    """Raise a clear error when a runtime version does not match."""
    if actual != expected:
        raise RuntimeError(
            f'{component} version mismatch: expected {expected}, got {actual}'
        )


def main():
    """Check Python, Django, MySQL, and Django system configuration."""
    _require(sys.version_info[:3], EXPECTED_PYTHON, 'Python')

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')

    import django
    from django.core.management import call_command
    from django.db import connection

    _require(django.VERSION[:2], EXPECTED_DJANGO, 'Django')

    django.setup()
    call_command('check')

    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        mysql_version = cursor.fetchone()[0].split('-')[0]

    expected_mysql = os.environ.get(
        'EXPECTED_MYSQL_VERSION', EXPECTED_MYSQL
    )
    _require(mysql_version, expected_mysql, 'MySQL')

    print(
        'Development environment verified: '
        f'Python {sys.version_info.major}.{sys.version_info.minor}.'
        f'{sys.version_info.micro}, Django {django.get_version()}, '
        f'MySQL {mysql_version}'
    )


if __name__ == '__main__':
    main()
