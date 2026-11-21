"""Contracts for the real, checkout-isolated Dev Container CLI rehearsal."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / '.github/scripts/smoke_devcontainer.py'


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location('devcontainer_smoke', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_workflow_runs_actual_lifecycle_and_scoped_cleanup():
    workflow = yaml.safe_load(
        (ROOT / '.github/workflows/dev-environment-ci.yml').read_text(),
    )
    job = workflow['jobs']['devcontainer-smoke']
    assert job['runs-on'] == 'ubuntu-24.04'
    assert job['timeout-minutes'] <= 30
    run = '\n'.join(step.get('run', '') for step in job['steps'])
    assert 'python3 .github/scripts/smoke_devcontainer.py' in run
    assert 'docker system prune' not in run
    assert 'sudo' not in run
    compatibility = workflow['jobs']['compatibility']['steps']
    tests = next(step['run'] for step in compatibility
                 if step.get('name') == 'Run application smoke tests')
    for filename in ('test_devcontainer_ci.py', 'test_development_docs.py',
                     'test_native_reset_safety.py',
                     'test_native_reset_reference_data.py'):
        assert filename in tests


def test_environment_does_not_import_a_personal_database_or_project(smoke):
    environment = smoke.clean_environment({
        'PATH': '/tools', 'HOME': '/user', 'DOCKER_CONTEXT': 'chosen',
        'DOCKER_CONFIG': '/isolated/docker-config',
        'COMPOSE_PROJECT_NAME': 'preserve', 'COMPOSE_FILE': '/preserve.yml',
        'MYSQL_PASSWORD': 'private', 'MYSQL_HOST': 'production',
        'GCD_WEB_PORT': '8001', 'DEV_UID': '0', 'USE_ELASTICSEARCH': 'true',
        'DJANGO_SETTINGS_MODULE': 'settings',
    })
    assert environment == {
        'PATH': '/tools', 'HOME': '/user', 'DOCKER_CONTEXT': 'chosen',
        'DOCKER_CONFIG': '/isolated/docker-config',
    }


def test_ci_pins_verified_compose_only_for_the_editor_job():
    jobs = yaml.safe_load(
        (ROOT / '.github/workflows/dev-environment-ci.yml').read_text(),
    )['jobs']
    job = jobs['devcontainer-smoke']
    # The runner context is available in step env, not job env.
    assert 'DOCKER_CONFIG' not in job.get('env', {})
    steps = job['steps']
    install = next(step for step in steps
                   if step['name'] == 'Install the tested Compose plugin')
    assert install['env'] == {
        'DOCKER_CONFIG': '${{ runner.temp }}/gcd-devcontainer-docker',
        'COMPOSE_VERSION': 'v5.7.1',
        'COMPOSE_SHA256': (
            'af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf'
        ),
    }
    assert steps.index(install) < next(
        index for index, step in enumerate(steps)
        if step['name'] == 'Rehearse an isolated Dev Container clone'
    )
    rehearse = next(
        step for step in steps
        if step['name'] == 'Rehearse an isolated Dev Container clone'
    )
    assert rehearse['env']['DOCKER_CONFIG'] == install['env']['DOCKER_CONFIG']
    assert not any('DOCKER_CONFIG' in other.get('env', {})
                   for name, other in jobs.items()
                   if name != 'devcontainer-smoke')
    assert 'BUILDX_BAKE_ENTITLEMENTS_FS' not in install['run']


@pytest.mark.parametrize('valid_checksum', [True, False])
def test_compose_install_checks_checksum_before_running_plugin(
        tmp_path, valid_checksum):
    """Run the workflow shell with local download/Docker stand-ins only."""
    job = yaml.safe_load(
        (ROOT / '.github/workflows/dev-environment-ci.yml').read_text(),
    )['jobs']['devcontainer-smoke']
    install = next(step for step in job['steps']
                   if step['name'] == 'Install the tested Compose plugin')
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    payload = tmp_path / 'downloaded-compose'
    payload.write_text("#!/bin/sh\nprintf '5.7.1\\n'\n")
    calls = tmp_path / 'docker-calls'
    for name, script in {
        'curl': '''
from pathlib import Path
import os
import sys
assert ('https://github.com/docker/compose/releases/download/v5.7.1/'
        'docker-compose-linux-x86_64') in sys.argv
destination = sys.argv[sys.argv.index('--output') + 1]
Path(destination).write_bytes(Path(os.environ['COMPOSE_TEST_PAYLOAD']).read_bytes())
''',
        'docker': '''
from pathlib import Path
import os
import subprocess
import sys
with open(os.environ['COMPOSE_TEST_CALLS'], 'a') as output:
    output.write(' '.join(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'compose':
    plugin = Path(os.environ['DOCKER_CONFIG']) / 'cli-plugins/docker-compose'
    raise SystemExit(subprocess.call([str(plugin), *sys.argv[2:]]))
assert sys.argv[1:] == ['buildx', 'version']
''',
    }.items():
        executable = binaries / name
        executable.write_text(f'#!{sys.executable}\n' + script)
        executable.chmod(0o755)
    environment = {
        'PATH': f'{binaries}:{os.environ["PATH"]}',
        **install['env'],
        'DOCKER_CONFIG': str(tmp_path / 'isolated config'),
        'COMPOSE_SHA256': (hashlib.sha256(payload.read_bytes()).hexdigest()
                           if valid_checksum else '0' * 64),
        'COMPOSE_TEST_PAYLOAD': str(payload),
        'COMPOSE_TEST_CALLS': str(calls),
    }
    result = subprocess.run(
        ['bash', '-euo', 'pipefail', '-c', install['run']],
        env=environment, text=True, capture_output=True, check=False,
    )
    if valid_checksum:
        assert result.returncode == 0, result.stderr
        assert calls.read_text().splitlines() == [
            'compose version --short', 'buildx version',
        ]
    else:
        assert result.returncode != 0
        assert not calls.exists(), 'Unverified plugin was executed'


def test_compose_uses_explicit_workspace_files_and_project(smoke, tmp_path):
    workspace = tmp_path / 'clone'
    command = smoke.compose(
        workspace, 'gcd-editor-abc', 'stop', '--timeout', '30',
    )
    assert command == [
        'docker', 'compose', '--project-directory', str(workspace),
        '--project-name', 'gcd-editor-abc',
        '-f', str(workspace / 'compose.yaml'),
        '-f', str(workspace / '.devcontainer/compose.yaml'),
        '-f', str(workspace / '.devcontainer/compose.project.yaml'),
        'stop', '--timeout', '30',
    ]


def test_probe_reads_assertions_from_the_selected_clone(smoke, tmp_path):
    probe = tmp_path / '.github/scripts/smoke_devcontainer_probe.py'
    probe.parent.mkdir(parents=True)
    committed_probe = "print('assertions from the selected committed clone')\n"
    probe.write_text(committed_probe)
    (tmp_path / '.devcontainer-smoke-marker').write_text(
        'non-root Dev Container persistence\n',
    )
    calls = []
    result = {'uid': os.getuid()}

    def run(command, **kwargs):
        calls.append(command)
        return 'GCD_DEVCONTAINER_RESULT=' + json.dumps(result)

    smoke.run = run
    assert smoke.probe(tmp_path, 'verify') == result
    assert calls == [[
        *smoke.CLI, 'exec', '--workspace-folder', str(tmp_path),
        'python', '-c', committed_probe, 'verify',
    ]]


def test_probe_never_falls_back_to_the_invoking_checkout(smoke, tmp_path):
    smoke.run = lambda *args, **kwargs: pytest.fail(
        'Missing committed probe must fail before invoking the CLI',
    )
    with pytest.raises(FileNotFoundError):
        smoke.probe(tmp_path, 'verify')


@pytest.mark.parametrize('changes', [
    {'com.docker.compose.project': 'another-project'},
    {'com.docker.compose.project.working_dir': '/another-checkout'},
    {'com.docker.compose.service': 'worker'},
])
def test_cleanup_refuses_unexpected_container_labels(smoke, tmp_path, changes):
    labels = {
        'com.docker.compose.project': 'gcd-editor-abc',
        'com.docker.compose.project.working_dir': str(tmp_path),
        'com.docker.compose.service': 'web',
    }
    labels.update(changes)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:3] == ['docker', 'ps', '-aq']:
            return 'container-id\n'
        if command[:2] == ['docker', 'inspect']:
            return json.dumps([{'Id': 'container-id', 'Config': {
                'Labels': labels,
            }}])
        pytest.fail(f'Unexpected mutating command: {command}')

    smoke.run = fake_run
    with pytest.raises(RuntimeError, match='Refusing'):
        smoke.stop_owned(tmp_path, 'gcd-editor-abc')
    assert len(calls) == 2


def test_cleanup_keeps_volumes_and_stops_only_owned_project(smoke, tmp_path):
    calls = []
    smoke.owned_containers = lambda *args: [{'Id': 'container-id'}]
    smoke.run = lambda command, **kwargs: calls.append(command)
    smoke.stop_owned(tmp_path, 'gcd-editor-abc')
    assert calls == [smoke.compose(
        tmp_path, 'gcd-editor-abc', 'stop', '--timeout', '30',
    )]
    assert all('down' not in call and '--volumes' not in call
               for call in calls)


def test_failure_during_initial_up_still_attempts_owned_stop(smoke, tmp_path):
    stopped = []
    smoke.run = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError('initial up failed'),
    )
    smoke.stop_owned = lambda *args: stopped.append(args)
    with pytest.raises(RuntimeError, match='initial up failed'):
        smoke.exercise(tmp_path, 'gcd-editor-abc')
    assert stopped == [(tmp_path, 'gcd-editor-abc')]


def test_default_cli_is_pinned_without_a_global_install(smoke):
    assert smoke.CLI == ['npx', '--yes', '@devcontainers/cli@0.91.0']


def test_timeout_ends_the_owned_cli_process_group(smoke, monkeypatch):
    signals = []
    created = []

    class Process:
        pid = 12345
        calls = 0

        def communicate(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise smoke.subprocess.TimeoutExpired(['test-cli'], 1)
            return ('', '')

    def popen(*args, **kwargs):
        created.append(kwargs)
        return Process()

    monkeypatch.setattr(smoke.subprocess, 'Popen', popen)
    monkeypatch.setattr(smoke.os, 'killpg',
                        lambda *arguments: signals.append(arguments))
    with pytest.raises(smoke.subprocess.TimeoutExpired):
        smoke.run(['test-cli'], timeout=1)
    assert created[0]['start_new_session'] is True
    assert signals == [(12345, smoke.signal.SIGTERM)]


def test_sigterm_stops_child_and_owned_project_then_exits_143(tmp_path):
    """Exercise main's signal handling with real processes, but no Docker."""
    ready = tmp_path / 'child-ready'
    stopped = tmp_path / 'child-stopped'
    cleanup = tmp_path / 'project-stopped'
    child = f'''
import os
from pathlib import Path
import signal
import time

def terminate(signum, frame):
    Path({str(stopped)!r}).write_text('terminated')
    raise SystemExit(0)

signal.signal(signal.SIGTERM, terminate)
Path({str(ready)!r}).write_text(str(os.getpid()))
while True:
    time.sleep(1)
'''
    driver = f'''
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('smoke', {str(SCRIPT)!r})
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
real_run = smoke.run
workspace = None

def run(command, **kwargs):
    global workspace
    if command[0] == 'npx':
        workspace = command[command.index('--workspace-folder') + 1]
        return real_run([sys.executable, '-c', {child!r}], timeout=60)
    if command[:3] == ['git', 'rev-parse', 'HEAD']:
        return 'test-head'
    if command[:3] == ['git', 'hash-object', '--stdin']:
        return 'test-project'
    if command[:3] == ['docker', 'ps', '-aq']:
        return 'owned-id' if workspace else ''
    if command[:2] == ['docker', 'inspect']:
        return json.dumps([{{'Config': {{'Labels': {{
            'com.docker.compose.project': 'gcd-editor-test-project',
            'com.docker.compose.project.working_dir': workspace,
            'com.docker.compose.service': 'web',
        }}}}}}])
    if command[:2] == ['docker', 'compose']:
        Path({str(cleanup)!r}).write_text(json.dumps(command))
    return ''

smoke.run = run
sys.argv = ['smoke', '--source', {str(tmp_path)!r},
            '--parent', {str(tmp_path)!r}]
smoke.main()
'''
    process = subprocess.Popen(
        [sys.executable, '-c', driver], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None:
            if time.monotonic() > deadline:
                pytest.fail('The owned test child did not become ready')
            time.sleep(0.02)
        if not ready.exists():
            pytest.fail(str(process.communicate(timeout=5)))
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=10) == 143
        process.communicate(timeout=5)
        assert stopped.read_text() == 'terminated'
        command = json.loads(cleanup.read_text())
        assert command[:2] == ['docker', 'compose']
        assert command[-3:] == ['stop', '--timeout', '30']
        assert command[command.index('--project-name') + 1] == (
            'gcd-editor-test-project'
        )
        assert '--volumes' not in command and 'down' not in command
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        if ready.exists():
            try:
                os.killpg(int(ready.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_probe_runs_real_http_and_requires_non_root_without_host_docker(smoke):
    probe = SCRIPT.with_name('smoke_devcontainer_probe.py').read_text()
    assert "os.getuid() != 0" in probe
    assert "'/var/run/docker.sock'" in probe
    assert "session.post(" in probe
    assert "settings.CSRF_COOKIE_NAME" in probe
    assert "Session.objects.get(" in probe
    assert "SHOW GRANTS" in probe
    assert "CREATE DATABASE" not in probe
    assert "GCD_DEVCONTAINER_RESULT=" in probe
