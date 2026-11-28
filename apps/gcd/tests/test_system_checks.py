"""
The system checks of the development settings report nothing but the
reCAPTCHA test keys, and only that check is silenced, see #454.
"""

import json
import subprocess
import sys
from pathlib import Path

from django.conf import settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RECAPTCHA_TEST_KEYS = 'django_recaptcha.recaptcha_test_key_error'


def _system_check_ids():
    """
    Run the system checks in a clean Python process: the test session
    also loads the dummy models of the tests, which the checks report too.
    run_checks ignores SILENCED_SYSTEM_CHECKS, so silenced checks count.
    """
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import django, json; django.setup(); '
            'from django.core import checks; '
            'print(json.dumps(sorted({m.id for m in checks.run_checks()})))',
        ],
        check=False,
        capture_output=True,
        cwd=PROJECT_ROOT,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def test_system_checks_report_only_the_recaptcha_test_keys():
    assert _system_check_ids() == [RECAPTCHA_TEST_KEYS]


def test_only_the_recaptcha_test_keys_check_is_silenced():
    assert settings.SILENCED_SYSTEM_CHECKS == [RECAPTCHA_TEST_KEYS]
