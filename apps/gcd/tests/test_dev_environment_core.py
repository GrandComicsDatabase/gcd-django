"""Contract tests for the one-clone core development environment."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
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


def test_compose_sizes_mysql_for_the_full_catalog_with_an_override():
    """Docker MySQL avoids the 128 MiB default but remains configurable."""
    database = _load_compose_file()['services']['db']

    assert database['command'] == [
        '--innodb-buffer-pool-size=${GCD_MYSQL_BUFFER_POOL_SIZE:-1G}'
    ]


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
    assert 'SET SESSION group_concat_max_len = 1000000;' in launcher


def _run_catalog_copy_with_fake_metadata(*missing_columns):
    """Run the copy helper against mocked MySQL commands."""
    launcher = _read_project_file('bin/dev')
    definition = launcher.split('copy_dump_catalog() {', 1)[1]
    body = definition.split('\n}\n', 1)[0]
    shell = textwrap.dedent('''
        set -euo pipefail
        MYSQL_DATABASE=gcd_dev_copy_test
        missing_columns="$1"
        mysql_root_query() {
          printf '%s\\n' "$1" >&2
          case "$1" in
            *'SELECT target.column_name'*) printf '%s' "$missing_columns" ;;
            *'group_concat_max_len'*) printf '%s\\n' 'COPY_CATALOG;' ;;
            *'AUTO_INCREMENT = 1'*) printf '%s\\n' 'RESET_AUTO_INCREMENT;' ;;
            *) return 99 ;;
          esac
        }
        mysql_root() { cat; }
    ''')
    shell += 'copy_dump_catalog() {' + body + '\n}\ncopy_dump_catalog\n'
    return subprocess.run(
        ['bash', '-c', shell, 'copy-dump-catalog', '\n'.join(missing_columns)],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        text=True,
    )


@pytest.mark.parametrize('missing_columns', [
    (), ('created',), ('modified',), ('created', 'modified'),
])
def test_series_bond_dump_copy_fills_only_missing_timestamps(missing_columns):
    """Only the missing Series Bond timestamps receive the shared baseline."""
    result = _run_catalog_copy_with_fake_metadata(*missing_columns)
    assert result.returncode == 0, result.stderr
    assert "WHERE target.table_schema = 'gcd_dev_copy_test'" in result.stderr
    assert "target.table_name = 'gcd_series_bond'" in result.stderr
    assert "source.table_schema = 'gcd_dev_import_stage'" in result.stderr
    assert 'source.column_name IS NULL' in result.stderr
    assert 'AND 2 = (' in result.stderr
    assert "column_type = 'datetime(6)' AND is_nullable = 'NO'" \
        in result.stderr

    columns = ''.join(f',`{column}`' for column in missing_columns)
    values = ',@gcd_series_bond_import_baseline' * len(missing_columns)
    assert f"IF(table_name = 'gcd_series_bond', '{columns}', '')" \
        in result.stderr
    assert f"IF(table_name = 'gcd_series_bond', '{values}', '')" \
        in result.stderr
    baseline = 'SET @gcd_series_bond_import_baseline = UTC_TIMESTAMP(6);'
    assert result.stdout.splitlines() == [
        'SET FOREIGN_KEY_CHECKS=0;',
        *([baseline] if missing_columns else []),
        'COPY_CATALOG;',
        'RESET_AUTO_INCREMENT;',
        'SET FOREIGN_KEY_CHECKS=1;',
    ]


def test_series_bond_dump_copy_refuses_unexpected_column_metadata():
    """Metadata outside the two literal column names must not reach SQL."""
    result = _run_catalog_copy_with_fake_metadata('other_column')
    assert result.returncode == 1
    assert 'Unexpected Series Bond timestamp column' in result.stderr
    assert 'group_concat_max_len' not in result.stderr
    assert result.stdout == ''


def test_dev_launcher_copies_catalog_keywords_by_content_type():
    """Dump keywords are linked through matching content types, not raw ids."""
    launcher = _read_project_file('bin/dev')
    setup_body = launcher.split('setup_dump_database() {', 1)[1]
    assert setup_body.index('copy_dump_catalog') < \
        setup_body.index('copy_dump_keywords')
    keywords = launcher.split('copy_dump_keywords() {', 1)[1] \
        .split('setup_dump_database() {', 1)[0]
    assert 'target_type.app_label = source_type.app_label' in keywords
    assert 'target_type.model = source_type.model' in keywords
    assert "WHERE source_type.app_label = 'gcd'" in keywords


def test_dev_launcher_handles_crlf_dotenv_and_native_database_overrides():
    """The .env parser supports Windows endings and native DB configuration."""
    launcher = _read_project_file('bin/dev')
    example_environment = _read_project_file('.env.example')

    assert 'GCD_MYSQL_BUFFER_POOL_SIZE' in launcher
    assert 'MYSQL_HOST MYSQL_PORT' in launcher
    assert 'line="${line%$\'\\r\'}"' in launcher
    assert 'GCD_MYSQL_BUFFER_POOL_SIZE=1G' in example_environment
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


def test_ci_exercises_native_setup_and_tests_as_a_scoped_user():
    """The compatibility job must exercise the launcher, not just manage.py."""
    job = _load_dev_environment_workflow()['jobs']['compatibility']
    env = job['env']
    assert env['MYSQL_USER'] != 'root'
    assert env['MYSQL_DATABASE'].startswith('gcd_dev_')
    assert job['services']['mysql']['env']['MYSQL_DATABASE'] == (
        env['MYSQL_DATABASE']
    )
    steps = [step.get('run', '') for step in job['steps']]
    smoke = steps.index('python .github/scripts/smoke_native_setup.py')
    assert not any('manage.py migrate' in step for step in steps[:smoke])
    assert any('./bin/dev --runtime native test' in step
               for step in steps[smoke + 1:])


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


@pytest.fixture
def native_launcher(tmp_path):
    """Run an isolated launcher with recording Python/Docker stand-ins."""
    project = tmp_path / 'project with spaces'
    binaries = project / 'bin'
    binaries.mkdir(parents=True)
    launcher = binaries / 'dev'
    launcher.write_text(_read_project_file('bin/dev'), encoding='utf-8')
    launcher.chmod(0o755)
    log = tmp_path / 'python-calls.jsonl'
    docker_log = tmp_path / 'docker-called'
    python = binaries / 'record-python'
    python.write_text(f'#!{sys.executable}\n' + textwrap.dedent('''
        import json
        import os
        import sys

        arguments = sys.argv[1:]
        if arguments[0] == '-c':
            stage = ('version' if 'sys.version_info' in arguments[1]
                     else 'database')
        elif arguments == ['scripts/check_dev_environment.py']:
            stage = 'verify'
        else:
            stage = {'seed_development_data': 'seed',
                     'runserver': 'server'}.get(arguments[1], arguments[1])
        with open(os.environ['NATIVE_TEST_LOG'], 'a') as output:
            output.write(json.dumps({
                'stage': stage, 'arguments': arguments, 'cwd': os.getcwd(),
                'environment': {key: os.environ.get(key) for key in (
                    'DJANGO_SETTINGS_MODULE', 'MYSQL_DATABASE', 'MYSQL_HOST',
                    'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD',
                    'USE_ELASTICSEARCH')},
            }) + '\\n')
        if stage == os.environ.get('NATIVE_TEST_FAIL_STAGE'):
            raise SystemExit(42)
        if stage == 'database':
            print(os.environ['NATIVE_TEST_DATABASE_NAME'])
    '''), encoding='utf-8')
    python.chmod(0o755)
    docker = binaries / 'docker'
    docker.write_text(
        '#!/bin/sh\nprintf called > "$NATIVE_TEST_DOCKER_LOG"\nexit 99\n',
        encoding='utf-8',
    )
    docker.chmod(0o755)

    def run(*arguments, environment=None, dotenv=None, cwd=None):
        """Keep shell configuration and every executable call test-local."""
        log.unlink(missing_ok=True)
        docker_log.unlink(missing_ok=True)
        env = {
            'PATH': f'{binaries}:/usr/bin:/bin',
            'PYTHON': str(python),
            'NATIVE_TEST_LOG': str(log),
            'NATIVE_TEST_DOCKER_LOG': str(docker_log),
            'NATIVE_TEST_DATABASE_NAME': 'gcd_dev',
        }
        env.update(environment or {})
        if dotenv is not None:
            (project / '.env').write_bytes(dotenv.encode('utf-8'))
        result = subprocess.run(
            [str(launcher), '--runtime', 'native', *arguments],
            env=env, cwd=cwd or project, capture_output=True, text=True,
            check=False,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()] \
            if log.exists() else []
        assert not docker_log.exists(), 'Native command invoked Docker'
        return result, calls

    return project, run


@pytest.mark.parametrize('database', [
    'gcd_dev', 'gcd_django_dev', 'gcd_dev_phase5_123',
])
def test_native_setup_orders_guard_migrate_seed_verify_and_server(
        native_launcher, database):
    """Native setup uses the selected DB, core settings, and foreground UI."""
    project, run = native_launcher
    result, calls = run('setup', environment={
        'NATIVE_TEST_DATABASE_NAME': database,
        'MYSQL_DATABASE': database,
        'MYSQL_HOST': '127.0.0.1', 'MYSQL_PORT': '13385',
        'MYSQL_USER': 'limited_user', 'MYSQL_PASSWORD': 'local_fixture',
        'GCD_WEB_PORT': '18086',
        'DJANGO_SETTINGS_MODULE': 'must_not_be_used',
        'USE_ELASTICSEARCH': 'true',
    })

    assert result.returncode == 0, result.stderr
    assert [call['stage'] for call in calls] == [
        'version', 'database', 'migrate', 'seed', 'verify', 'server',
    ]
    assert calls[2]['arguments'] == ['manage.py', 'migrate', '--noinput']
    assert calls[3]['arguments'] == ['manage.py', 'seed_development_data']
    assert calls[5]['arguments'] == [
        'manage.py', 'runserver', '127.0.0.1:18086',
    ]
    for call in calls[1:]:
        assert call['cwd'] == str(project)
        assert call['environment'] == {
            'DJANGO_SETTINGS_MODULE': 'settings_dev',
            'MYSQL_DATABASE': database,
            'MYSQL_HOST': '127.0.0.1', 'MYSQL_PORT': '13385',
            'MYSQL_USER': 'limited_user', 'MYSQL_PASSWORD': 'local_fixture',
            'USE_ELASTICSEARCH': 'false',
        }
    assert 'http://127.0.0.1:18086' in result.stdout
    assert 'docs/development/CORE_SETUP.md' in result.stdout
    assert 'development' in result.stdout.lower()


@pytest.mark.parametrize('database', [
    'production', 'gcd_ci', '', 'gcd_dev_', 'gcd_dev_UPPER',
    'gcd_dev;DROP', ' gcd_dev', 'gcd_dev\nproduction',
    'gcd_dev\n', 'gcd_dev_phase5\n\n',
])
def test_native_setup_rejects_actual_unsafe_database_before_mutation(
        native_launcher, database):
    """A safe environment name cannot mask an unsafe Django-selected DB."""
    _, run = native_launcher
    result, calls = run('setup', environment={
        'MYSQL_DATABASE': 'gcd_dev',
        'NATIVE_TEST_DATABASE_NAME': database,
    })

    assert result.returncode == 2
    assert 'setup only permits' in result.stderr
    assert [call['stage'] for call in calls] == ['version', 'database']


def test_native_setup_guard_uses_django_name_not_environment_name(
        native_launcher):
    """The actual configured database is the authority for the guard."""
    _, run = native_launcher
    result, calls = run('setup', environment={
        'MYSQL_DATABASE': 'not_the_selected_database',
        'NATIVE_TEST_DATABASE_NAME': 'gcd_dev_actual',
    })

    assert result.returncode == 0, result.stderr
    assert calls[-1]['stage'] == 'server'


@pytest.mark.parametrize('stage', [
    'version', 'database', 'migrate', 'seed', 'verify', 'server',
])
def test_native_setup_stops_at_each_failed_stage(native_launcher, stage):
    """Failures propagate and no later setup stage is attempted."""
    _, run = native_launcher
    result, calls = run('setup', environment={'NATIVE_TEST_FAIL_STAGE': stage})
    stages = ['version', 'database', 'migrate', 'seed', 'verify', 'server']

    assert result.returncode == (1 if stage == 'version' else 42)
    assert [call['stage'] for call in calls] == (
        stages[:stages.index(stage) + 1]
    )
    if stage != 'server':
        assert 'GCD is available' not in result.stdout


@pytest.mark.parametrize('arguments', [
    ('--dump',), ('--dump', ''), ('--dump', 'sample.zip'),
    ('--replace',), ('--yes',), ('--replace', '--yes'), ('--unknown',),
])
def test_native_setup_rejects_options_before_python_or_docker(
        native_launcher, arguments):
    """Native bootstrap cannot silently accept destructive/import options."""
    _, run = native_launcher
    result, calls = run('setup', *arguments)

    assert result.returncode == 2
    assert './bin/dev setup --dump ARCHIVE' in result.stderr
    assert calls == []


def test_native_setup_runs_from_other_directory_with_relative_python(
        native_launcher, tmp_path):
    """Setup resolves the interpreter and commands within its checkout."""
    project, run = native_launcher
    result, calls = run(
        'setup', environment={'PYTHON': 'bin/record-python'}, cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert all(call['cwd'] == str(project) for call in calls)
    assert calls[-1]['arguments'][-1] == '127.0.0.1:8000'
    assert calls[-1]['environment']['MYSQL_PORT'] == '3308'


def test_native_setup_dotenv_is_literal_and_shell_overrides_win(
        native_launcher, tmp_path):
    """CRLF .env values are literal, with existing shell values preferred."""
    _, run = native_launcher
    marker = tmp_path / 'must-not-be-created'
    password = f'$(touch "{marker}")'
    result, calls = run(
        'setup', environment={'MYSQL_PORT': '14444'},
        dotenv=(f'MYSQL_PASSWORD={password}\r\nMYSQL_PORT=13333\r\n'
                'MYSQL_HOST=127.0.0.2\r\nGCD_WEB_PORT=18087\r\n'),
    )

    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert calls[-1]['environment']['MYSQL_PASSWORD'] == password
    assert calls[-1]['environment']['MYSQL_PORT'] == '14444'
    assert calls[-1]['environment']['MYSQL_HOST'] == '127.0.0.2'
    assert calls[-1]['arguments'][-1] == '127.0.0.1:18087'


def test_native_setup_rejects_unallowlisted_dotenv_key(native_launcher):
    """New setup does not weaken shared configuration parsing."""
    _, run = native_launcher
    result, calls = run('setup', dotenv='DJANGO_SETTINGS_MODULE=other\n')

    assert result.returncode == 2
    assert 'Unsupported .env variable' in result.stderr
    assert calls == []


def test_native_up_still_skips_seeding_and_keeps_explicit_search_setting(
        native_launcher):
    """Opting into native setup does not change the existing native up path."""
    _, run = native_launcher
    result, calls = run('up', environment={'USE_ELASTICSEARCH': 'true'})

    assert result.returncode == 0, result.stderr
    assert [call['stage'] for call in calls] == [
        'version', 'migrate', 'server',
    ]
    assert calls[-1]['environment']['USE_ELASTICSEARCH'] == 'true'


def test_native_reset_retains_its_narrower_database_guard(native_launcher):
    """Allowing suffixed setup databases must not authorize flushing them."""
    _, run = native_launcher
    result, calls = run('reset', '--yes', environment={
        'NATIVE_TEST_DATABASE_NAME': 'gcd_dev_phase5',
    })

    assert result.returncode == 2
    assert ('Native reset only permits gcd_dev or gcd_django_dev'
            in result.stderr)
    assert [call['stage'] for call in calls] == ['version', 'database']
