"""Contract tests for the one-clone core development environment."""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_project_file(relative_path):
    """Read a repository file as UTF-8 text."""
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def _load_compose_file():
    """Load the Compose definition under test."""
    return yaml.safe_load(_read_project_file('compose.yaml'))


def _load_dev_environment_workflow():
    """Load the development-environment CI workflow under test."""
    return yaml.safe_load(
        _read_project_file('.github/workflows/dev-environment-ci.yml')
    )


def _run_dev(*arguments):
    """Run the development launcher without invoking a shell."""
    return subprocess.run(
        [str(PROJECT_ROOT / 'bin' / 'dev'), *arguments],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        text=True,
    )


def _read_search_settings(**overrides):
    """Read development search settings in a clean Python process."""
    environment = os.environ.copy()
    for key in (
        'USE_ELASTICSEARCH', 'ELASTICSEARCH_URL', 'REDIS_HOST', 'REDIS_PORT'
    ):
        environment.pop(key, None)
    environment.update(overrides)
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import json, settings_dev as settings; '
            'print(json.dumps({'
            '"enabled": settings.USE_ELASTICSEARCH, '
            '"url": settings.HAYSTACK_CONNECTIONS["default"]["URL"], '
            '"signal": getattr(settings, "HAYSTACK_SIGNAL_PROCESSOR", None), '
            '"django_rq": "django_rq" in settings.INSTALLED_APPS, '
            '"redis_host": settings.RQ_QUEUES["default"]["HOST"], '
            '"redis_port": settings.RQ_QUEUES["default"]["PORT"]}))',
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_compose_defines_the_core_services_and_local_only_ports():
    """The core stack has database, migration, and web services."""
    compose = _load_compose_file()

    assert compose['name'] == 'gcd-django-dev'
    assert {'db', 'migrate', 'web'} <= set(compose['services'])
    assert compose['services']['db']['image'] == 'mysql:8.0'
    assert compose['services']['db']['ports'] == [
        '127.0.0.1:${GCD_MYSQL_PORT:-3308}:3306'
    ]
    assert compose['services']['web']['ports'] == [
        '127.0.0.1:${GCD_WEB_PORT:-8000}:8000'
    ]
    assert compose['services']['db'].get('container_name') is None
    assert 'mysql_data' in compose['volumes']


def test_compose_defines_opt_in_search_services():
    """Search services are pinned, health-gated, and excluded from core use."""
    compose = _load_compose_file()
    services = compose['services']

    assert services['elasticsearch']['image'] == (
        'docker.elastic.co/elasticsearch/elasticsearch:7.17.29'
    )
    assert services['elasticsearch']['profiles'] == ['search']
    assert services['elasticsearch']['ports'] == [
        '127.0.0.1:${GCD_ELASTICSEARCH_PORT:-9200}:9200'
    ]
    assert services['elasticsearch']['environment']['discovery.type'] == \
        'single-node'
    assert services['elasticsearch']['environment']['ES_JAVA_OPTS'] == \
        '-Xms512m -Xmx512m'
    assert services['elasticsearch']['healthcheck']['test'][0] == 'CMD-SHELL'

    assert services['redis']['image'] == 'redis:7.4-alpine'
    assert services['redis']['profiles'] == ['search']
    assert services['redis']['healthcheck']['test'] == [
        'CMD', 'redis-cli', 'ping'
    ]

    assert services['worker']['profiles'] == ['search']
    assert services['worker']['depends_on']['elasticsearch'] == {
        'condition': 'service_healthy'
    }
    assert services['worker']['depends_on']['redis'] == {
        'condition': 'service_healthy'
    }
    assert services['worker']['command'] == \
        'python manage.py rqworker default'
    assert {'mysql_data', 'elasticsearch_data', 'redis_data'} <= \
        set(compose['volumes'])


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
    """Healthchecks safely handle credentials and retain clear commands."""
    services = _load_compose_file()['services']

    assert services['db']['healthcheck']['test'] == [
        'CMD-SHELL',
        'mysql --protocol=TCP -h localhost -u"$$MYSQL_USER" '
        '-p"$$MYSQL_PASSWORD" --database="$$MYSQL_DATABASE" '
        '--execute="SELECT 1" >/dev/null',
    ]
    assert services['web']['healthcheck']['test'] == [
        'CMD-SHELL',
        "python -c \"from urllib.request import urlopen; "
        "urlopen('http://127.0.0.1:8000/health/', timeout=3)\"",
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
    assert './bin/dev search-up' in result.stdout
    assert './bin/dev search-rebuild' in result.stdout
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


def test_dev_launcher_validates_dump_before_replacing_database():
    """Invalid dump paths and extensions cannot trigger a database reset."""
    launcher = _read_project_file('bin/dev')
    setup_body = launcher.split('setup_docker_environment() {', 1)[1]
    assert 'validate_dump_archive "$archive"' in setup_body
    assert setup_body.index('validate_dump_archive "$archive"') < \
        setup_body.index('fresh_docker_database')
    assert 'The dump must be a .zip archive or .sql file.' in launcher


def test_dev_launcher_allows_long_catalog_column_lists():
    """Dump table-copy SQL is not truncated by MySQL's default limit."""
    launcher = _read_project_file('bin/dev')
    assert 'SET SESSION group_concat_max_len = 1000000; SELECT CONCAT' \
        in launcher


def test_dev_launcher_handles_crlf_dotenv_and_native_database_overrides():
    """The .env parser supports Windows endings and native DB configuration."""
    launcher = _read_project_file('bin/dev')
    example_environment = _read_project_file('.env.example')

    assert 'MYSQL_HOST MYSQL_PORT' in launcher
    assert 'line="${line%$\'\\r\'}"' in launcher
    assert 'MYSQL_HOST=127.0.0.1' in example_environment
    assert 'MYSQL_PORT=3308' in example_environment


def test_dev_launcher_declares_single_command_search_workflows():
    """Search startup and rebuilding remain explicit, reusable operations."""
    launcher = _read_project_file('bin/dev')

    assert 'enable_docker_search' in launcher
    assert 'compose --profile search up -d --build --wait' in launcher
    assert 'rebuild_index --noinput' in launcher
    assert 'GCD_SEARCH_WORKERS:-4' in launcher
    assert 'search_arguments+=(--batch-size 1000)' in launcher
    assert 'search_arguments+=(--workers "$search_workers")' in launcher
    assert 'compose --profile search down' in launcher
    assert launcher.count('compose --profile search down --volumes') == 2


def test_development_search_settings_are_disabled_by_default():
    """The core environment never requires Elasticsearch or Redis."""
    settings = _read_search_settings()

    assert settings == {
        'enabled': False,
        'url': 'http://127.0.0.1:9200/',
        'signal': None,
        'django_rq': False,
        'redis_host': 'localhost',
        'redis_port': 6379,
    }


def test_development_search_settings_enable_existing_queue_backend():
    """Search mode uses the existing Haystack RQ signal processor."""
    settings = _read_search_settings(
        USE_ELASTICSEARCH='true',
        ELASTICSEARCH_URL='http://elasticsearch:9200/',
        REDIS_HOST='redis',
        REDIS_PORT='6380',
    )

    assert settings == {
        'enabled': True,
        'url': 'http://elasticsearch:9200/',
        'signal': 'haystack_rqueue.signals.RQueueSignalProcessor',
        'django_rq': True,
        'redis_host': 'redis',
        'redis_port': 6380,
    }


def test_ci_rebuilds_and_verifies_the_optional_search_environment():
    """CI exercises indexing, queries, and queued updates on Ubuntu 24.04."""
    workflow = _load_dev_environment_workflow()
    job = workflow['jobs']['search-smoke']

    assert job['runs-on'] == 'ubuntu-24.04'
    commands = '\n'.join(
        str(step.get('run', '')) for step in job['steps']
    )
    assert './bin/dev setup --replace --yes' in commands
    assert './bin/dev search-rebuild' in commands
    assert 'verify_development_search' in commands
    assert 'docker compose --profile search down --volumes' in commands
