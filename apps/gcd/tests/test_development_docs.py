"""Contributor entry points and safe, current development-guide contracts."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[3]
GUIDES = (
    'README.md',
    'docs/development/CORE_SETUP.md',
    'docs/development/NATIVE_COMMON.md',
    'docs/development/NATIVE_MACOS.md',
    'docs/development/NATIVE_UBUNTU.md',
    'docs/development/WSL2.md',
    'docs/development/DEV_CONTAINER.md',
    'docs/development/SUPPORTED_VERSIONS.md',
    'docs/development/TROUBLESHOOTING.md',
    'docs/Getting_Started.md',
    'docs/Getting_Started_on_MacOS_or_Linux.md',
    'docs/Getting_Started_on_Windows.md',
)
LEGACY = GUIDES[-3:]


def _heading_anchors(path):
    """GitHub-style anchors for the plain headings used in these guides."""
    text = re.sub(r'^```.*?^```', '', path.read_text(encoding='utf-8'),
                  flags=re.M | re.S)
    seen = {}
    anchors = set()
    for heading in re.findall(r'^#{1,6}\s+(.+)$', text, re.M):
        slug = re.sub(r'[^\w\s-]', '', heading.lower()).replace(' ', '-')
        occurrence = seen.get(slug, 0)
        seen[slug] = occurrence + 1
        anchors.add(f'{slug}-{occurrence}' if occurrence else slug)
    return anchors


@pytest.mark.parametrize('filename', GUIDES)
def test_development_guide_local_links_resolve(filename):
    path = ROOT / filename
    text = path.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^\s)]+)\)', text):
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        destination = ((path.parent / unquote(url.path)).resolve()
                       if url.path else path)
        assert destination.is_relative_to(ROOT), (filename, target)
        assert destination.is_file(), (filename, target)
        if url.fragment and destination.suffix == '.md':
            assert unquote(url.fragment) in _heading_anchors(destination), (
                filename, target,
            )


@pytest.mark.parametrize('filename', GUIDES)
def test_development_bash_examples_parse(filename):
    text = (ROOT / filename).read_text(encoding='utf-8')
    for example in re.findall(r'^```bash\n(.*?)^```', text, re.M | re.S):
        result = subprocess.run(
            ['bash', '-n'], input=example, text=True, capture_output=True,
            check=False,
        )
        assert result.returncode == 0, (filename, result.stderr)


@pytest.mark.parametrize('filename', LEGACY)
def test_retired_guides_redirect_without_obsolete_install_commands(filename):
    text = (ROOT / filename).read_text(encoding='utf-8')
    assert 'retired' in text.lower()
    assert '(development/CORE_SETUP.md)' in text
    assert '```' not in text
    for obsolete in ('easy_install', 'Python 3.8', 'mysql -ugcdonline',
                     'Review Board', 'gcd-django-docker'):
        assert obsolete not in text


def test_windows_entry_points_link_the_explicit_wsl2_guide():
    assert '(docs/development/WSL2.md)' in (ROOT / 'README.md').read_text()
    assert '(WSL2.md)' in (
        ROOT / 'docs/development/CORE_SETUP.md'
    ).read_text()
    assert '(development/WSL2.md)' in (
        ROOT / 'docs/Getting_Started_on_Windows.md'
    ).read_text()


def test_wsl2_guide_separates_native_success_from_editor_and_docker_coverage():
    text = ' '.join((ROOT / 'docs/development/WSL2.md').read_text().split())
    assert 'wsl --install -d Ubuntu-24.04' in text
    assert 'wsl --list --verbose' in text
    assert '(NATIVE_COMMON.md#4-start-the-sample-environment)' in text
    assert 'Linux filesystem' in text
    assert 'pinned source archive' in text
    assert 'Docker Desktop' in text and 'not yet been validated' in text
    assert 'systemd' in text and 'localhost' in text
    assert 'Do not disable the firewall' in text
    assert 'wsl --unregister' not in text


def test_wsl2_native_route_uses_one_canonical_startup_step():
    section = (ROOT / 'docs/development/WSL2.md').read_text().split(
        '## 3A. Native Ubuntu without Docker',
    )[1].split('## 3B.')[0]
    assert '(NATIVE_COMMON.md#4-start-the-sample-environment)' in section
    commands = re.findall(r'^```bash\n(.*?)^```', section, re.M | re.S)
    assert not any('--runtime native setup' in command for command in commands)


def test_docker_setup_warning_explains_unprompted_empty_database_replacement():
    text = ' '.join(
        (ROOT / 'docs/development/CORE_SETUP.md').read_text().split(),
    )
    assert 'When MySQL has no tables, setup skips confirmation' in text
    assert 'still removes' in text
    assert 'MySQL, Elasticsearch and Redis volumes' in text


def test_codespaces_is_explicitly_deferred_not_a_supported_setup_choice():
    for filename in ('CORE_SETUP.md', 'DEV_CONTAINER.md'):
        text = (ROOT / 'docs/development' / filename).read_text()
        assert re.search(r'Codespaces.{0,100}deferred', text, re.S), filename
    chooser = (ROOT / 'docs/development/CORE_SETUP.md').read_text()
    assert not any('Codespaces' in line for line in chooser.splitlines()
                   if line.startswith('|'))


def test_supported_mysql_floor_is_distinct_from_native_package_choices():
    text = (ROOT / 'docs/development/SUPPORTED_VERSIONS.md').read_text()
    assert 'mysql@8.4' in text
    assert 'Ubuntu 24.04' in text
    assert '`>=8.0`' in text
    assert '8.0' in text and 'compatibility floor' in text
