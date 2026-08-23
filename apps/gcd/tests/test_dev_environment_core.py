"""Contract tests for the one-clone core development environment."""

import subprocess
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_project_file(relative_path):
    """Read a repository file as UTF-8 text."""
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def _load_compose_file():
    """Load the Compose definition under test."""
    return yaml.safe_load(_read_project_file('compose.yaml'))


def _run_dev(*arguments):
    """Run the development launcher without invoking a shell."""
    return subprocess.run(
        [str(PROJECT_ROOT / 'bin' / 'dev'), *arguments],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        text=True,
    )


def test_compose_defines_the_core_services_and_local_only_ports():
    """The core stack has database, migration, and web services."""
    compose = _load_compose_file()

    assert compose['name'] == 'gcd-django-dev'
    assert set(compose['services']) == {'db', 'migrate', 'web'}
    assert compose['services']['db']['image'] == 'mysql:8.0'
    assert compose['services']['db']['ports'] == [
        '127.0.0.1:${GCD_MYSQL_PORT:-3308}:3306'
    ]
    assert compose['services']['web']['ports'] == [
        '127.0.0.1:${GCD_WEB_PORT:-8000}:8000'
    ]
    assert compose['services']['db'].get('container_name') is None
    assert compose['volumes'] == {'mysql_data': None}


def test_compose_waits_for_database_and_migrations_before_web_starts():
    """Startup is health-gated rather than relying on a polling script."""
    services = _load_compose_file()['services']

    assert services['db']['healthcheck']['test'][0] == 'CMD-SHELL'
    assert services['migrate']['depends_on']['db'] == {
        'condition': 'service_healthy'
    }
    assert 'migrate --noinput' in services['migrate']['command']
    assert services['web']['depends_on']['migrate'] == {
        'condition': 'service_completed_successfully'
    }
    assert 'runserver 0.0.0.0:8000' in services['web']['command']


def test_compose_healthchecks_quote_credentials_and_remain_readable():
    """Healthchecks safely handle credentials and retain a clear web command."""
    services = _load_compose_file()['services']

    assert services['db']['healthcheck']['test'] == [
        'CMD-SHELL',
        "mysqladmin ping -h localhost -u'$$MYSQL_USER' -p'$$MYSQL_PASSWORD'",
    ]
    assert services['web']['healthcheck']['test'] == [
        'CMD-SHELL',
        "python -c \"from urllib.request import urlopen; "
        "urlopen('http://127.0.0.1:8000/', timeout=3)\"",
    ]


def test_development_image_uses_the_supported_python_line():
    """The Docker image is built from the supported Python release line."""
    dockerfile = _read_project_file('Dockerfile.dev')

    assert dockerfile.startswith('FROM python:3.13-slim-bookworm')
    assert 'setuptools<81' in dockerfile
    assert 'default-libmysqlclient-dev' in dockerfile
    assert 'git' in dockerfile
    assert 'libicu-dev' in dockerfile


def test_dev_launcher_documents_supported_commands():
    """The launcher gives contributors a usable command reference."""
    result = _run_dev('help')

    assert result.returncode == 0
    assert './bin/dev up' in result.stdout
    assert './bin/dev setup' in result.stdout
    assert './bin/dev setup --dump ~/Downloads/current.zip' in result.stdout
    assert '--runtime native' in result.stdout
    assert 'reset --yes' in result.stdout


def test_dev_launcher_refuses_reset_without_explicit_confirmation():
    """The destructive reset command cannot run accidentally."""
    result = _run_dev('reset')

    assert result.returncode != 0
    assert '--yes' in result.stderr


def test_dev_launcher_declares_a_confirmation_gated_dump_setup_flow():
    """Full-catalog setup stays a single command without silent replacement."""
    launcher = _read_project_file('bin/dev')

    assert 'setup [--dump ARCHIVE] [--replace --yes]' in launcher
    assert 'setup_dump_database' in launcher
    assert 'seed_development_data' in launcher
    assert 'A non-empty local database will be replaced' in launcher


def test_dev_launcher_handles_crlf_dotenv_and_native_database_overrides():
    """The .env parser supports Windows endings and native DB configuration."""
    launcher = _read_project_file('bin/dev')
    example_environment = _read_project_file('.env.example')

    assert 'MYSQL_HOST MYSQL_PORT' in launcher
    assert 'line="${line%$\'\\r\'}"' in launcher
    assert 'MYSQL_HOST=127.0.0.1' in example_environment
    assert 'MYSQL_PORT=3308' in example_environment
