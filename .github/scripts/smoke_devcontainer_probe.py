"""Sample, real HTTP login, permissions and persistence in the editor."""

import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time

import django
import requests


assert Path.cwd() == Path('/workspace')
assert os.getuid() != 0 and os.getuid() == os.geteuid()
assert pwd.getpwuid(os.getuid()).pw_name == 'gcd'
assert Path.home() == Path('/home/gcd')
assert not Path('/var/run/docker.sock').exists()
assert not os.environ.get('MYSQL_ROOT_PASSWORD')
assert not os.environ.get('MYSQL_PWD')
assert os.environ['DJANGO_SETTINGS_MODULE'] == 'settings_dev'
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sessions.models import Session  # noqa: E402
from django.db import connection  # noqa: E402
from django.urls import reverse  # noqa: E402
from apps.gcd.models import Issue, Series  # noqa: E402

assert settings.DATABASES['default']['HOST'] == 'db'
assert settings.DATABASES['default']['NAME'] == 'gcd_dev'
assert not settings.USE_ELASTICSEARCH
assert Series.objects.count() == 1 and Issue.objects.count() == 2
with connection.cursor() as cursor:
    cursor.execute(
        'SELECT DATABASE(), CURRENT_USER(), @@innodb_buffer_pool_size',
    )
    database, account, pool = cursor.fetchone()
    assert (database, account, pool) == ('gcd_dev', 'gcd_dev@%', 1073741824)
    cursor.execute('SHOW GRANTS')
    grants = [row[0] for row in cursor.fetchall()]
assert len(grants) == 3, grants
assert sum(grant.startswith('GRANT USAGE ON *.* TO ') for grant in grants) == 1
assert any('ON `gcd\\_dev`.*' in grant for grant in grants), grants
assert any('ON `test\\_gcd\\_dev`.*' in grant for grant in grants), grants
assert not any('WITH GRANT OPTION' in grant for grant in grants)

subprocess.run(['python', 'scripts/check_dev_environment.py'], check=True)
subprocess.run(['python', 'manage.py', 'check'], check=True)
subprocess.run(['python', 'manage.py', 'migrate', '--check'], check=True)
subprocess.run(['python', '-m', 'pip', 'check'], check=True)

origin = 'http://127.0.0.1:8000'
with requests.Session() as session:
    session.trust_env = False
    deadline = time.monotonic() + 60
    while True:
        try:
            response = session.get(origin + '/health/', timeout=3)
            assert response.status_code == 200
            assert response.json() == {'status': 'ok'}
            break
        except (requests.RequestException, AssertionError):
            if time.monotonic() > deadline:
                raise
            time.sleep(1)
    assert session.get(origin + '/', timeout=10).status_code == 200
    path = reverse('login')
    assert session.get(origin + path, timeout=10).status_code == 200
    response = session.post(origin + path, data={
        'username': 'editor', 'password': 'editme', 'next': '/',
        'csrfmiddlewaretoken': session.cookies[settings.CSRF_COOKIE_NAME],
    }, headers={'Referer': origin + path}, timeout=10,
        allow_redirects=False)
    assert response.status_code == 302
    key = session.cookies[settings.SESSION_COOKIE_NAME]
    authenticated = Session.objects.get(session_key=key).get_decoded()
    assert authenticated['_auth_user_id'] == str(
        User.objects.get(username='editor').pk,
    )

marker = Path('.devcontainer-smoke-marker')
sentinel_name = 'devcontainer_smoke_persistence'
if sys.argv[1] == 'create':
    assert not marker.exists()
    assert not User.objects.filter(username=sentinel_name).exists()
    User.objects.create_user(username=sentinel_name)
    marker.write_text('non-root Dev Container persistence\n')
else:
    assert sys.argv[1] == 'verify'
    assert marker.read_text() == 'non-root Dev Container persistence\n'
extension_home = Path.home() / '.vscode-server'
extension_home.mkdir(exist_ok=True)
(extension_home / 'gcd-smoke-write').write_text('non-root extension home\n')

print('GCD_DEVCONTAINER_RESULT=' + json.dumps({
    'uid': os.getuid(), 'home': str(Path.home()),
    'series': list(Series.objects.values_list('pk', flat=True)),
    'issues': list(Issue.objects.values_list('pk', flat=True)),
    'sentinel_user_id': User.objects.get(username=sentinel_name).pk,
    'health_home_csrf_login': 'passed', 'scoped_grants': 'passed',
    'workspace_extension_writes': 'passed',
}, sort_keys=True))
