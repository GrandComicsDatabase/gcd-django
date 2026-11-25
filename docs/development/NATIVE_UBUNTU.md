# Native development on Ubuntu 24.04 LTS

Docker is not required. Python, MySQL and Django run directly on Ubuntu.
After the one-time prerequisites, continue with the shared native setup
command to migrate the database, add sample data and start the site. For
other choices, see [Core setup](CORE_SETUP.md).

The clean sample-data walkthrough passed on **Ubuntu 24.04.5 ARM64**, using
Python 3.13.18 and Ubuntu's MySQL 8.0.46. It covered dependency installation,
tests, sample login/edit/approval, repeat setup and MySQL restart persistence.
The same native recipe also passed on Ubuntu 24.04.5 x86_64 under Windows WSL2,
including Windows-browser access, file saves and distro-restart persistence.
That run used a pinned source archive. A standalone x86_64 Ubuntu installation
has not had a clean walkthrough; ordinary Linux CI is separate evidence. This guide
does not validate native full-dump import or native search. Consult the
[supported version policy](SUPPORTED_VERSIONS.md) when selecting packages.

## 1. Install the system prerequisites

These instructions are for a new, dedicated local development installation.
Before changing packages, check for an existing MySQL-compatible server,
including stopped services and retained data. Check installed server packages,
`/var/lib/mysql`, `/etc/mysql`, and any known custom data directories or ports.
If another application uses the server, stop and review that installation;
do not replace its packages, reuse its data directory or change its settings
to follow this guide.

On the fresh installation:

```bash
sudo apt update
sudo apt install git build-essential default-libmysqlclient-dev mysql-server libicu-dev pkg-config curl ca-certificates gettext
```

Use Ubuntu 24.04's packaged MySQL 8.0 for this route. MySQL 8.0 remains the
project's compatibility floor; this guide does not add Oracle's APT repository
or upgrade an existing server to obtain 8.4. See the
[Ubuntu MySQL guide](https://ubuntu.com/server/docs/how-to/databases/install-mysql/)
and [Ubuntu 24.04's MySQL package listing](https://packages.ubuntu.com/search?keywords=mysql-server-8.0&searchon=names&suite=noble&section=all).

## 2. Install Python 3.13 without replacing system Python

Use `uv` only to obtain Python 3.13. Application dependencies still use a
standard `.venv`, pip and the repository's `requirements.txt`.

Install `uv` with its official installer. The command downloads and executes
the vendor's script; inspect it first if your machine's software policy
requires that, or choose another method from the
[official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Follow the installer's PATH instructions and open a new terminal, then run:

```bash
uv python install 3.13
```

Do not replace `/usr/bin/python3`, use `sudo pip` or add a PPA for this setup.
The project requires Python 3.13 even when the distribution interpreter has
a different version. See [uv's version-specific Python installation](https://docs.astral.sh/uv/guides/install-python/).

## 3. Configure local MySQL

These commands use Ubuntu's systemd service manager. Start the dedicated
local server, then create a uniquely named configuration backup. The editor
opens only if that backup succeeds:

```bash
sudo systemctl enable --now mysql
mysql_config_file=/etc/mysql/mysql.conf.d/mysqld.cnf
mysql_config_backup="$(sudo mktemp "${mysql_config_file}.before-gcd.XXXXXXXX")" &&
  sudo cp -p "$mysql_config_file" "$mysql_config_backup" &&
  printf 'Backup: %s\n' "$mysql_config_backup" &&
  sudoedit "$mysql_config_file"
```

Keep the printed backup path. In the file's existing `[mysqld]` section,
retain unrelated options and add or update these settings. Do not add a
second copy of the section:

```ini
[mysqld]
bind-address=127.0.0.1
mysqlx-bind-address=127.0.0.1
innodb_buffer_pool_size=1G
```

Both listeners must remain local. A 1 GiB buffer pool is the recommended
starting point for Docker and native development alike. Native setup does
not edit this file or enforce that value. Use `512M` on a memory-constrained
machine, allowing room for other MySQL allocations and the application.
This is not a production sizing rule. See [MySQL's buffer-pool documentation](https://dev.mysql.com/doc/refman/8.4/en/innodb-buffer-pool-resize.html).

Restart after saving:

```bash
sudo systemctl restart mysql
sudo systemctl status mysql --no-pager
```

A successful service-manager message is not a database-readiness check.
Before provisioning a database or starting Django, confirm that the local
administrator connection succeeds with `sudo mysql`; exit that prompt when
done. After the application account exists, use its TCP connection check in
the shared guide. If a start or restart briefly refuses a connection, wait
a few seconds and retry the check. If it persists, inspect the service and
error log rather than resetting data or repeatedly restarting the service.

If `systemctl` reports that the system was not booted with systemd, stop and
check the actual host environment before proceeding. Windows contributors
should follow [the WSL2 guide](WSL2.md), including its systemd and
Windows-browser checks, before continuing this native recipe.

## 4. Get the project and create a virtual environment

Run this from the parent directory for a new checkout. Use `beta` for normal
development, or the review branch specified by a maintainer:

```bash
git clone --branch beta https://github.com/GrandComicsDatabase/gcd-django.git
cd gcd-django
"$(uv python find 3.13)" -m venv .venv
```

Do not clone over an existing checkout or replace its virtual environment.
Continue with [Shared native setup](NATIVE_COMMON.md) to install the Python
dependencies, provision the development database and account, and start the
sample site.

## Service controls

Ctrl-C stops Django. MySQL is a separate service and may remain running.
These commands affect every database hosted by the local MySQL instance,
not only GCD:

```bash
sudo systemctl stop mysql
sudo systemctl start mysql
sudo journalctl -u mysql -n 50 --no-pager
```

For connection, dependency or startup errors, see
[Troubleshooting](TROUBLESHOOTING.md).
