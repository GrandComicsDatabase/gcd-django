# Core development environment

This is the supported one-clone setup for working on `gcd-django`. It runs the
application with Python 3.13 and MySQL 8.0. Elasticsearch, sample data, image
fixtures, and optional service integrations are intentionally outside this
first setup layer.

## Docker (default)

Install Docker Desktop, clone this repository, and run:

```bash
./bin/dev up
```

The application is available at <http://127.0.0.1:8000>. MySQL is available
only on `127.0.0.1:3308` from the local machine. The database data lives in the
Docker volume named `gcd-django-dev_mysql_data`.

Useful commands:

```bash
./bin/dev doctor
./bin/dev test
./bin/dev manage createsuperuser
./bin/dev logs web
./bin/dev down
```

To change local ports or development-only credentials, copy `.env.example` to
`.env` and edit literal `KEY=VALUE` entries. Shell expressions are deliberately
not evaluated. Do not use production credentials in this file.

`./bin/dev reset --yes` removes the local Docker database volume and starts a
fresh database. It is intentionally confirmation-gated.

## Native (Docker-free)

Docker is not required. Install Python 3.13, MySQL 8.0 or newer, Git, and the
system packages needed to compile the project dependencies. Create a database
and user, then point the launcher at it. The native defaults expect a MySQL
server exposed on local port 3308 so they work with the Docker database too.

On Ubuntu 24.04, install the build prerequisites with:

```bash
sudo apt-get update
sudo apt-get install -y build-essential default-libmysqlclient-dev git libicu-dev pkg-config
```

On macOS with Homebrew, install them with:

```bash
brew install icu4c@78 mysql-client pkgconf
export PKG_CONFIG_PATH="$(brew --prefix icu4c@78)/lib/pkgconfig:$(brew --prefix mysql-client)/lib/pkgconfig"
```

Keep the `export` line in the shell session used for dependency installation,
or add it to the environment activation script for your local virtual
environment. Do not set `ICU_VERSION`: PyICU uses `pkg-config` to obtain the
required compiler and linker flags on macOS.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip "setuptools<81"
.venv/bin/python -m pip install -r requirements.txt

MYSQL_PORT=3306 PYTHON=.venv/bin/python ./bin/dev --runtime native up
```

The equivalent native commands are:

```bash
MYSQL_PORT=3306 PYTHON=.venv/bin/python ./bin/dev --runtime native doctor
MYSQL_PORT=3306 PYTHON=.venv/bin/python ./bin/dev --runtime native test
MYSQL_PORT=3306 PYTHON=.venv/bin/python ./bin/dev --runtime native manage createsuperuser
```

Native `reset --yes` only operates on a database named `gcd_dev` or
`gcd_django_dev`; it flushes that database and reapplies migrations. Set
`MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD` in your shell or `.env`
when your local MySQL credentials differ from the development defaults.
