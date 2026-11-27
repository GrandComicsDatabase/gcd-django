"""Fail-closed contracts for the Dev Container's MySQL init hook."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INIT_SCRIPT = PROJECT_ROOT / '.devcontainer' / 'init-test-database.sh'


@pytest.fixture
def init_hook(tmp_path):
    """Capture SQL without connecting to a database or storing secrets."""
    capture = tmp_path / 'mysql-calls.jsonl'
    client = tmp_path / 'mysql'
    client.write_text(
        f'#!{sys.executable}\n'
        'import json, os, sys\n'
        'with open(os.environ["MYSQL_CAPTURE"], "a") as stream:\n'
        '    stream.write(json.dumps({"args": sys.argv[1:], '
        '"sql": sys.stdin.read(), '
        '"password_provided": bool(os.environ.get("MYSQL_PWD"))}) + "\\n")\n'
        'if "--execute=SELECT @@GLOBAL.partial_revokes" in sys.argv:\n'
        '    print(os.environ.get("FAKE_PARTIAL_REVOKES", "0"))\n'
        'sys.exit(int(os.environ.get("FAKE_MYSQL_EXIT", "0")))\n',
        encoding='utf-8',
    )
    client.chmod(0o755)

    def invoke(**overrides):
        environment = os.environ.copy()
        environment.update({
            'PATH': f'{tmp_path}{os.pathsep}{environment["PATH"]}',
            'MYSQL_CAPTURE': str(capture),
            'MYSQL_DATABASE': 'gcd_dev',
            'MYSQL_USER': 'gcd_dev',
            'MYSQL_ROOT_PASSWORD': 'disposable-test-only',
        })
        environment.update(overrides)
        result = subprocess.run(
            ['bash', str(INIT_SCRIPT)], input='', text=True,
            capture_output=True, env=environment, check=False,
        )
        calls = []
        if capture.exists():
            calls = [json.loads(line)
                     for line in capture.read_text().splitlines()]
        assert 'disposable-test-only' not in result.stdout + result.stderr
        return result, calls

    return invoke


@pytest.mark.parametrize('database', [
    'gcd_dev', 'gcd_dev_editor', 'gcd_django_dev', 'gcd_dev_' + 'a' * 51,
])
def test_init_hook_scopes_both_database_grants(init_hook, database):
    """
    Replace any image-created grants with two literal database grants and
    SELECT on the two Performance Schema lock tables.
    """
    result, calls = init_hook(MYSQL_DATABASE=database)

    assert result.returncode == 0, result.stderr
    assert len(calls) == 2
    assert calls[0]['args'] == [
        '--protocol=socket', '--user=root', '--batch', '--skip-column-names',
        '--execute=SELECT @@GLOBAL.partial_revokes',
    ]
    assert calls[1]['args'] == [
        '--protocol=socket', '--user=root', '--batch', '--skip-column-names',
    ]
    escaped = database.replace('_', '\\_')
    assert calls[1]['sql'].strip() == (
        "REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'gcd_dev'@'%';\n"
        f"GRANT ALL PRIVILEGES ON `{escaped}`.* TO 'gcd_dev'@'%';\n"
        f"GRANT ALL PRIVILEGES ON `test\\_{escaped}`.* TO 'gcd_dev'@'%';\n"
        "GRANT SELECT ON performance_schema.data_locks TO 'gcd_dev'@'%';\n"
        "GRANT SELECT ON performance_schema.data_lock_waits "
        "TO 'gcd_dev'@'%';"
    )
    assert all(call['password_provided'] for call in calls)
    assert 'WITH GRANT OPTION' not in calls[1]['sql']
    assert 'ON *.*' not in calls[1]['sql']


@pytest.mark.parametrize('database', [
    '', 'production', 'gcd_dev%;', 'gcd_dev`', 'gcd_dev\n',
    'gcd_dev_é', 'gcd_dev_' + 'a' * 52,
])
def test_init_hook_rejects_unsafe_database_before_mysql(init_hook, database):
    result, calls = init_hook(MYSQL_DATABASE=database)
    assert result.returncode == 2
    assert 'development database' in result.stderr
    assert calls == []


@pytest.mark.parametrize('username', [
    '', 'root', "gcd'@'%';", 'gcd_dev\n', 'a' * 33,
])
def test_init_hook_rejects_unsafe_account_before_mysql(init_hook, username):
    result, calls = init_hook(MYSQL_USER=username)
    assert result.returncode == 2
    assert 'application user' in result.stderr
    assert calls == []


@pytest.mark.parametrize('partial_revokes', ['1', '', 'unrecognized'])
def test_init_hook_refuses_unknown_grant_semantics(init_hook, partial_revokes):
    result, calls = init_hook(FAKE_PARTIAL_REVOKES=partial_revokes)
    assert result.returncode == 2
    assert 'partial_revokes=OFF' in result.stderr
    assert len(calls) == 1


def test_init_hook_stops_when_database_probe_fails(init_hook):
    result, calls = init_hook(FAKE_MYSQL_EXIT='7')
    assert result.returncode == 7
    assert len(calls) == 1


def test_init_hook_requires_a_root_password_without_printing_it(init_hook):
    result, calls = init_hook(MYSQL_ROOT_PASSWORD='')
    assert result.returncode == 2
    assert 'MYSQL_ROOT_PASSWORD is required' in result.stderr
    assert calls == []


def test_init_hook_is_executable_for_the_mysql_entrypoint():
    """Execute the hook separately instead of sourcing its shell settings."""
    assert os.access(INIT_SCRIPT, os.X_OK)
