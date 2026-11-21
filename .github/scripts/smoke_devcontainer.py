"""Rehearse the actual CLI in a fresh local clone, retaining stopped evidence.

Requires Git, Docker Compose and Node/npm. Uses committed source HEAD only.
Never runs Compose against the invoking checkout, deletes volumes or prunes.
"""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


CLI = ['npx', '--yes', '@devcontainers/cli@0.91.0']
ROOT = Path(__file__).resolve().parents[2]


def clean_environment(environment):
    """Do not carry personal project/database overrides into the clone."""
    return {key: value for key, value in environment.items()
            if not key.startswith(('COMPOSE_', 'MYSQL_', 'GCD_', 'DEV_'))
            and key not in ('USE_ELASTICSEARCH', 'DJANGO_SETTINGS_MODULE')}


def exit_on_sigterm(signum, frame):
    """Unwind through child-process and project cleanup on termination."""
    raise SystemExit(128 + signum)


def run(command, *, cwd=None, input=None, timeout=900, show_output=True):
    print('+ ' + ' '.join(map(str, command[:8])), flush=True)
    process = subprocess.Popen(
        list(map(str, command)), cwd=cwd, text=True, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, env=clean_environment(os.environ),
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(input=input, timeout=timeout)
    except BaseException:
        # An interrupted npx/CLI may own Compose children. End that command's
        # process group before the caller checks/stops its Docker project.
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)
        except ProcessLookupError:
            process.wait(timeout=5)
        raise
    if show_output and output:
        print(output, end='', flush=True)
    if process.returncode:
        raise subprocess.CalledProcessError(
            process.returncode, command, output,
        )
    return output


def compose(workspace, project, *arguments):
    return [
        'docker', 'compose', '--project-directory', str(workspace),
        '--project-name', project,
        '-f', str(workspace / 'compose.yaml'),
        '-f', str(workspace / '.devcontainer/compose.yaml'),
        '-f', str(workspace / '.devcontainer/compose.project.yaml'),
        *arguments,
    ]


def owned_containers(workspace, project):
    ids = run([
        'docker', 'ps', '-aq', '--filter',
        f'label=com.docker.compose.project={project}',
    ]).split()
    if not ids:
        return []
    records = json.loads(run(['docker', 'inspect', *ids], show_output=False))
    for record in records:
        labels = record['Config']['Labels']
        if (labels.get('com.docker.compose.project') != project or
                labels.get('com.docker.compose.project.working_dir') !=
                str(workspace) or
                labels.get('com.docker.compose.service') not in
                ('db', 'migrate', 'web')):
            raise RuntimeError('Refusing unexpected resource ownership')
    return records


def stop_owned(workspace, project):
    """Stop verified project containers on success or failure; keep data."""
    if owned_containers(workspace, project):
        run(compose(workspace, project, 'stop', '--timeout', '30'), timeout=90)


def identities(workspace, project):
    records = owned_containers(workspace, project)
    by_service = {}
    for record in records:
        service = record['Config']['Labels']['com.docker.compose.service']
        if service in by_service:
            raise RuntimeError(f'Multiple owned {service} containers')
        by_service[service] = record['Id']
        if any(record['NetworkSettings']['Ports'].values()):
            raise RuntimeError('Editor project unexpectedly publishes a port')
        if record['HostConfig']['Privileged']:
            raise RuntimeError('Editor project unexpectedly runs privileged')
    if set(by_service) != {'db', 'migrate', 'web'}:
        raise RuntimeError('Expected exactly the three editor services')
    return by_service


def probe(workspace, phase):
    probe_path = workspace / '.github/scripts/smoke_devcontainer_probe.py'
    output = run([
        *CLI, 'exec', '--workspace-folder', str(workspace),
        'python', '-c', probe_path.read_text(), phase,
    ], timeout=180)
    results = [line.removeprefix('GCD_DEVCONTAINER_RESULT=')
               for line in output.splitlines()
               if line.startswith('GCD_DEVCONTAINER_RESULT=')]
    if len(results) != 1:
        raise RuntimeError('Missing or ambiguous runtime result')
    result = json.loads(results[0])
    marker = workspace / '.devcontainer-smoke-marker'
    if marker.read_text() != 'non-root Dev Container persistence\n':
        raise RuntimeError('Host cannot read the editor-created file')
    if sys.platform.startswith('linux'):
        if (result['uid'] != os.getuid() or
                marker.stat().st_uid != os.getuid()):
            raise RuntimeError('Linux editor UID/host file ownership mismatch')
    return result


def exercise(workspace, project):
    """Real startup, application tests, reopen and forced web recreation."""
    up = [*CLI, 'up', '--workspace-folder', str(workspace)]
    try:
        run(up)
        initial_ids = identities(workspace, project)
        initial = probe(workspace, 'create')
        run([
            *CLI, 'exec', '--workspace-folder', str(workspace),
            'python', '-m', 'pytest', '-q',
            'apps/gcd/tests/test_devcontainer.py',
            'apps/gcd/tests/test_devcontainer_database.py',
            'apps/gcd/tests/test_health.py',
            'apps/gcd/tests/test_seed_development_data.py',
            'apps/gcd/tests/test_markdown_startup.py',
            'apps/gcd/tests/test_notes_rendering.py',
        ])
        stop_owned(workspace, project)
        run(up)
        if probe(workspace, 'verify') != initial:
            raise RuntimeError('Reopen changed the expected sample/marker')
        identities(workspace, project)
        run([*up, '--remove-existing-container'])
        rebuilt_ids = identities(workspace, project)
        if (rebuilt_ids['db'] != initial_ids['db'] or
                rebuilt_ids['web'] == initial_ids['web']):
            raise RuntimeError('Expected only the editor to be replaced')
        if probe(workspace, 'verify') != initial:
            raise RuntimeError('Rebuild changed the expected sample/marker')
    finally:
        stop_owned(workspace, project)
    records = owned_containers(workspace, project)
    if any(record['State']['Running'] for record in records):
        raise RuntimeError('Owned project did not stop')
    print('DEVCONTAINER_SMOKE_PASS (stopped, data retained)', flush=True)


def main():
    signal.signal(signal.SIGTERM, exit_on_sigterm)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--parent', type=Path,
                        help='Existing directory for the retained test clone')
    args = parser.parse_args()
    if os.getuid() == 0:
        parser.error('Run as the normal non-root contributor/runner user')
    source = args.source.resolve(strict=True)
    parent = args.parent.resolve(strict=True) if args.parent else None
    workspace = Path(tempfile.mkdtemp(
        prefix='gcd-devcontainer-smoke-', dir=parent,
    )).resolve() / 'source'
    run(['git', 'clone', '--quiet', '--local', '--no-hardlinks',
         str(source), str(workspace)])
    head = run(['git', 'rev-parse', 'HEAD'], cwd=workspace).strip()
    project = 'gcd-editor-' + run(
        ['git', 'hash-object', '--stdin'], cwd=workspace,
        input=str(workspace.resolve()),
    ).strip()
    # Both container and volume labels must be absent before any start command.
    for command in (
        ['docker', 'ps', '-aq'], ['docker', 'volume', 'ls', '-q'],
    ):
        if run([*command, '--filter',
                f'label=com.docker.compose.project={project}']).strip():
            raise RuntimeError('Refusing an existing project or volume')
    print(json.dumps({'workspace': str(workspace), 'project': project,
                      'source_head': head}), flush=True)
    exercise(workspace, project)


if __name__ == '__main__':
    main()
