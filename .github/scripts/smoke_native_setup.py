"""Start the native launcher on the disposable CI database and check HTTP."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def stop_server(server):
    """Stop the whole session's process group, including the autoreloader."""
    try:
        os.killpg(server.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            server.poll()  # Reap the parent even if a child is still alive.
            os.killpg(server.pid, 0)
            time.sleep(0.1)
        os.killpg(server.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # The entire group is already gone.
    finally:
        server.wait(timeout=5)


def main():
    target = tuple(os.environ.get(key) for key in (
        'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_HOST',
    ))
    if target != ('gcd_dev_ci', 'native_ci', '127.0.0.1'):
        sys.exit('Expected the disposable native CI database on loopback')

    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'

    # Inherit stdout/stderr so failures leave the launcher output in CI.
    server = subprocess.Popen(
        ['./bin/dev', '--runtime', 'native', 'setup'],
        env=dict(os.environ, PYTHON=sys.executable, GCD_WEB_PORT=str(port)),
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if server.poll() is not None:
                sys.exit(f'Native setup exited early: {server.returncode}')
            try:
                with urlopen(base + '/health/', timeout=3) as response:
                    if (response.status != 200 or
                            json.load(response) != {'status': 'ok'}):
                        sys.exit('Unexpected native health response')
                break
            except HTTPError:
                raise  # An HTTP error is a response, not a startup delay.
            except URLError:
                time.sleep(1)
        else:
            sys.exit('Native setup did not become ready within five minutes')
        with urlopen(base + '/', timeout=10) as response:
            if response.status != 200:
                sys.exit(f'Unexpected home page status: {response.status}')
    finally:
        stop_server(server)


if __name__ == '__main__':
    main()
