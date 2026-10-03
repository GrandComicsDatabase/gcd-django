# Core development environment

This is the supported one-clone setup for working on `gcd-django`. It runs the
application with Python 3.13 and MySQL 8.0. Elasticsearch and optional service
integrations remain opt-in.

## Docker (default)

Install Docker Desktop, clone this repository, and run:

```bash
./bin/dev up
```

The application is available at <http://127.0.0.1:8000>. MySQL is available
only on `127.0.0.1:3308` from the local machine. The database data lives in the
Docker volume named `gcd-django-dev_mysql_data`.

## Ready-to-use development data

For a small, deterministic local dataset, use one command instead of running
migrations, fixtures, and account setup separately:

```bash
./bin/dev setup
```

It creates the development database, applies migrations, loads local
development accounts, seeds a small relationship-rich catalog, creates a
dummy cover image and approved change-history comment, initializes global
statistics, and starts the application. The sample records are marked
`[GCD DEV]` so they are easy to find and safe to recreate.

The seeded accounts are deliberately public local-development fixtures. They
work only in this local database and must never be used for beta or production:

| Username | Password | Intended use |
| --- | --- | --- |
| `admin` | `admin` | Local Django superuser and administrator |
| `editor` | `editme` | Editor, indexer, and member workflow testing |
| `dexter_1234` | `test` | Standard indexer workflow testing |
| `anon` | — | Anonymous fixture account; it cannot log in |

### Full GCD catalog dump

The full catalog dump is optional. Download it manually from
<https://www.comics.org/download/> after accepting the GCD download terms, then
run:

```bash
./bin/dev setup --dump ~/Downloads/current.zip
```

The command handles everything else: it validates the archive, restores it to
a temporary local staging database, creates a clean migrated development
database, checks compatibility, copies catalog data, initializes local
accounts/statistics, and starts the site. It does not need a database name,
manual SQL command, fake migration, or separate seed step from the
contributor.

If a local database already exists, `setup` asks once before replacing it. For
non-interactive use, supply the explicit confirmation:

```bash
./bin/dev setup --dump ~/Downloads/current.zip --replace --yes
```

The full-dump workflow is currently supported by the default Docker runtime.
It needs approximately 12 GB of free Docker storage while the temporary
staging database and final development database coexist. The public dump does
not contain uploaded cover/image files; development uses the deterministic fake
image created by `seed_development_data` instead. The dump also does not
replace the local migration ledger, accounts, statistics, or change-history
fixtures.

Useful commands:

```bash
./bin/dev doctor
./bin/dev setup
./bin/dev test
./bin/dev manage createsuperuser
./bin/dev logs web
./bin/dev down
```

## Optional Elasticsearch search

The existing Haystack indexes and Elasticsearch 7 backend can run as an
optional extension of the core environment. For the first search-enabled
startup, or after replacing the development database, run:

```bash
./bin/dev search-rebuild
```

This one command starts Elasticsearch 7.17, Redis, the RQ index-update worker,
and the application, then rebuilds the search index with a batch size of 1,000
and four workers. Rebuilding a full catalog dump can still take several hours;
the deterministic sample dataset completes quickly. You can override the
defaults with Haystack options such as `--workers 2`, or set
`GCD_SEARCH_WORKERS` in `.env` for the local machine.

After an index exists, preserve and reuse it with:

```bash
./bin/dev search-up
```

Search data and queued jobs live in Docker volumes and survive normal
`./bin/dev down` / `search-up` cycles. The normal `./bin/dev up` command keeps
search disabled and does not start Elasticsearch, Redis, or the worker.

To change local ports or development-only credentials, including the
Elasticsearch host port, copy `.env.example` to `.env` and edit literal
`KEY=VALUE` entries. Shell expressions are deliberately not evaluated. Do not
use production credentials in this file.

`./bin/dev reset --yes` removes the local Docker database, Elasticsearch, and
Redis volumes and starts a fresh core database. It is intentionally
confirmation-gated.

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
