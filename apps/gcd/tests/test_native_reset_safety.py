"""Destructive native reset must validate the exact selected database."""

import pytest

from apps.gcd.tests.test_dev_environment_core import (
    native_launcher as _native_launcher,
)

native_launcher = _native_launcher


@pytest.mark.parametrize('database', [
    'gcd_dev', 'gcd_django_dev',
])
def test_native_reset_flushes_only_after_exact_database_guard(
        native_launcher, database):
    _, run = native_launcher
    result, calls = run('reset', '--yes', environment={
        'NATIVE_TEST_DATABASE_NAME': database,
    })
    assert result.returncode == 0, result.stderr
    assert [call['stage'] for call in calls] == [
        'version', 'database', 'flush', 'migrate',
        'restore_development_reference_data',
    ]
    assert calls[2]['arguments'] == ['manage.py', 'flush', '--noinput']
    assert calls[3]['arguments'] == ['manage.py', 'migrate', '--noinput']
    assert calls[4]['arguments'] == [
        'manage.py', 'restore_development_reference_data',
    ]


@pytest.mark.parametrize('database', [
    '', 'production', 'gcd_dev_other', ' gcd_dev', 'gcd_dev ',
    'gcd_dev\n', 'gcd_dev\n\n', 'gcd_django_dev\n', 'gcd_dev\nproduction',
])
def test_native_reset_does_not_normalize_unsafe_database_names(
        native_launcher, database):
    _, run = native_launcher
    result, calls = run('reset', '--yes', environment={
        'MYSQL_DATABASE': 'gcd_dev',
        'NATIVE_TEST_DATABASE_NAME': database,
    })
    assert result.returncode == 2
    assert 'Native reset only permits' in result.stderr
    assert [call['stage'] for call in calls] == ['version', 'database']


@pytest.mark.parametrize('arguments', [
    (), ('--unknown',), ('--yes', '--unknown'), ('--yes', '--yes'),
    ('--yes', 'production'),
])
def test_native_reset_requires_exact_confirmation_before_python(
        native_launcher, arguments):
    _, run = native_launcher
    result, calls = run('reset', *arguments)
    assert result.returncode == 2
    assert calls == []


@pytest.mark.parametrize('stage', [
    'version', 'database', 'flush', 'migrate',
    'restore_development_reference_data',
])
def test_native_reset_stops_after_each_failure(native_launcher, stage):
    _, run = native_launcher
    result, calls = run('reset', '--yes', environment={
        'NATIVE_TEST_FAIL_STAGE': stage,
    })
    stages = ['version', 'database', 'flush', 'migrate',
              'restore_development_reference_data']
    assert result.returncode == (1 if stage == 'version' else 42)
    assert [call['stage'] for call in calls] == (
        stages[:stages.index(stage) + 1]
    )
