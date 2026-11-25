"""Local editor-container contracts, without starting Docker or a database."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_devcontainer_reuses_core_and_waits_for_finite_setup():
    config = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
    assert config['dockerComposeFile'] == [
        '../compose.yaml', 'compose.yaml', 'compose.project.yaml',
    ]
    assert config['service'] == 'web'
    assert config['runServices'] == ['db', 'migrate', 'web']
    assert config['workspaceFolder'] == '/workspace'
    assert config['remoteUser'] == 'gcd'
    assert config['updateRemoteUserUID'] is True
    assert config['overrideCommand'] is False
    assert config['shutdownAction'] == 'stopCompose'
    assert config['waitFor'] == 'postCreateCommand'
    assert config['initializeCommand'] == [
        'bash', '.devcontainer/initialize.sh',
    ]
    assert config['postCreateCommand'] == [
        'bash', '.devcontainer/post-create.sh',
    ]
    assert config['forwardPorts'] == [8000]
    assert config['otherPortsAttributes']['onAutoForward'] == 'ignore'
    assert not any(config.get(key) for key in (
        'privileged', 'capAdd', 'securityOpt', 'mounts', 'features',
    ))
    assert config['customizations']['vscode']['extensions'] == [
        'ms-python.python', 'ms-python.vscode-pylance',
    ]


def test_editor_override_is_narrow_and_does_not_publish_database_ports():
    # Compose's reset tag clears inherited host ports, not the service itself.
    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor('!reset', lambda loader, node: [])
    override_text = (ROOT / '.devcontainer/compose.yaml').read_text()
    # An ordinary empty list would merge with the inherited host ports.
    assert override_text.count('ports: !reset []') == 2
    override = yaml.load(override_text, Loader=Loader)
    assert set(override) == {'services'}
    services = override['services']
    assert set(services) == {'db', 'migrate', 'web'}
    assert services['web'] == {
        'user': 'gcd', 'ports': [],
        'environment': {'USE_ELASTICSEARCH': 'false'},
    }
    assert services['migrate'] == {
        'environment': {'USE_ELASTICSEARCH': 'false'},
    }
    assert services['db'] == {
        'ports': [],
        'volumes': [
            './.devcontainer/init-test-database.sh:'
            '/docker-entrypoint-initdb.d/10-gcd-test-database.sh:ro',
        ],
    }
    dockerfile = (ROOT / 'Dockerfile.dev').read_text()
    assert 'groupadd --gid 1000 gcd' in dockerfile
    assert ('useradd --uid 1000 --gid gcd --create-home --shell /bin/bash gcd'
            in dockerfile)
    assert 'NOPASSWD' not in dockerfile


def _initializer(tmp_path, monkeypatch):
    workspace = tmp_path / 'checkout with spaces'
    folder = workspace / '.devcontainer'
    folder.mkdir(parents=True)
    shutil.copyfile(
        ROOT / '.devcontainer/initialize.sh', folder / 'initialize.sh',
    )
    tools = tmp_path / 'tools'
    tools.mkdir()
    docker = tools / 'docker'
    docker.write_text(
        '#!/bin/sh\n'
        'printf "%s\\n" "$*" >> "$DOCKER_CALLS"\n'
        'case "$*" in\n'
        '  *" config"*)\n'
        '    if [ -n "$CONFIG_EXIT" ]; then\n'
        '      exit "$CONFIG_EXIT"\n'
        '    elif [ "$MISSING_PROJECT" = "1" ]; then\n'
        '      printf "services:\\n  db:\\n    name: nested-only\\n"\n'
        '    elif [ -n "$EFFECTIVE_PROJECT" ]; then\n'
        '      printf "name: %s\\n" "$EFFECTIVE_PROJECT"\n'
        '    else\n'
        '      cat .devcontainer/compose.project.yaml\n'
        '    fi ;;\n'
        '  *) exit 91 ;;\n'
        'esac\n'
    )
    docker.chmod(0o755)
    monkeypatch.setenv('PATH', str(tools) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('DOCKER_CALLS', str(tmp_path / 'docker-calls'))
    monkeypatch.delenv('COMPOSE_PROJECT_NAME', raising=False)
    monkeypatch.delenv('EFFECTIVE_PROJECT', raising=False)
    monkeypatch.delenv('CONFIG_EXIT', raising=False)
    monkeypatch.delenv('MISSING_PROJECT', raising=False)
    return workspace


def _initialize(workspace):
    return subprocess.run(
        ['bash', '.devcontainer/initialize.sh'], cwd=workspace,
        capture_output=True, text=True, check=False,
    )


def test_initialize_is_stable_checkout_specific_and_read_only_to_docker(
    tmp_path, monkeypatch,
):
    workspace = _initializer(tmp_path, monkeypatch)
    first = _initialize(workspace)
    assert first.returncode == 0, first.stderr
    generated = workspace / '.devcontainer/compose.project.yaml'
    initial = generated.read_text()
    assert initial.startswith('name: gcd-editor-')
    assert _initialize(workspace).returncode == 0
    assert generated.read_text() == initial
    moved = tmp_path / 'another checkout'
    workspace.rename(moved)
    assert _initialize(moved).returncode == 0
    assert (moved / '.devcontainer/compose.project.yaml').read_text() \
        != initial
    calls = (tmp_path / 'docker-calls').read_text().splitlines()
    assert len(calls) == 3
    assert all(call.endswith(' config') for call in calls)


@pytest.mark.parametrize('source', ['environment', 'dotenv'])
def test_initialize_rejects_project_override_without_touching_it(
    tmp_path, monkeypatch, source,
):
    workspace = _initializer(tmp_path, monkeypatch)
    dotenv = workspace / '.env'
    dotenv.write_text('COMPOSE_PROJECT_NAME=gcd-django-dev\n')
    if source == 'environment':
        monkeypatch.setenv('COMPOSE_PROJECT_NAME', 'gcd-django-dev')
    else:
        monkeypatch.setenv('EFFECTIVE_PROJECT', 'gcd-django-dev')
    result = _initialize(workspace)
    assert result.returncode != 0
    assert 'COMPOSE_PROJECT_NAME' in result.stderr
    assert dotenv.read_text() == 'COMPOSE_PROJECT_NAME=gcd-django-dev\n'


def test_initialize_refuses_generated_file_symlinks(tmp_path, monkeypatch):
    workspace = _initializer(tmp_path, monkeypatch)
    preserved = tmp_path / 'preserved.yaml'
    preserved.write_text('name: preserved-project\n')
    (workspace / '.devcontainer/compose.project.yaml').symlink_to(preserved)
    result = _initialize(workspace)
    assert result.returncode != 0
    assert 'symlink' in result.stderr
    assert preserved.read_text() == 'name: preserved-project\n'
    assert not (tmp_path / 'docker-calls').exists()


@pytest.mark.parametrize('failure', ['nonzero', 'missing-name'])
def test_initialize_refuses_failed_or_incomplete_compose_config(
    tmp_path, monkeypatch, failure,
):
    workspace = _initializer(tmp_path, monkeypatch)
    if failure == 'nonzero':
        monkeypatch.setenv('CONFIG_EXIT', '17')
    else:
        monkeypatch.setenv('MISSING_PROJECT', '1')
    result = _initialize(workspace)
    assert result.returncode != 0
    assert 'Dev Container project:' not in result.stdout
    calls = (tmp_path / 'docker-calls').read_text().splitlines()
    assert len(calls) == 1
    assert calls[0].endswith(' config')


def test_initialize_uses_canonical_path_through_checkout_symlinks(
    tmp_path, monkeypatch,
):
    workspace = _initializer(tmp_path, monkeypatch)
    first = _initialize(workspace)
    assert first.returncode == 0, first.stderr
    generated = workspace / '.devcontainer/compose.project.yaml'
    original = generated.read_text()
    alias = tmp_path / 'checkout alias'
    alias.symlink_to(workspace, target_is_directory=True)
    second = _initialize(alias)
    assert second.returncode == 0, second.stderr
    assert generated.read_text() == original


def test_ci_runs_the_editor_contracts_in_compatibility_smoke():
    workflow = yaml.safe_load(
        (ROOT / '.github/workflows/dev-environment-ci.yml').read_text(),
    )
    step = next(
        step for step in workflow['jobs']['compatibility']['steps']
        if step.get('name') == 'Run application smoke tests'
    )
    for filename in ('test_devcontainer.py', 'test_devcontainer_database.py'):
        assert f'apps/gcd/tests/{filename}' in step['run']


def test_post_create_uses_only_seed_and_doctor_and_stops_on_failure(
    tmp_path, monkeypatch,
):
    tools = tmp_path / 'tools'
    tools.mkdir()
    python = tools / 'python'
    python.write_text(
        '#!/bin/sh\n'
        'printf "%s\\n" "$*" >> "$PYTHON_CALLS"\n'
        'exit "${PYTHON_EXIT:-0}"\n'
    )
    python.chmod(0o755)
    calls = tmp_path / 'calls'
    monkeypatch.setenv('PATH', str(tools) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('PYTHON_CALLS', str(calls))
    script = ROOT / '.devcontainer/post-create.sh'
    result = subprocess.run(['bash', str(script)], check=False)
    assert result.returncode == 0
    expected = [
        'manage.py seed_development_data', 'scripts/check_dev_environment.py',
    ]
    assert calls.read_text().splitlines() == expected
    monkeypatch.setenv('PYTHON_EXIT', '7')
    result = subprocess.run(['bash', str(script)], check=False)
    assert result.returncode == 7
    assert calls.read_text().splitlines() == expected + expected[:1]
