# Core development environment

Start with Docker Compose for the shortest setup. Choose a native guide to run
Python and MySQL directly on your computer without Docker. These are local
development workflows, not production deployment instructions.

| Your preference | Start here |
| --- | --- |
| One container-based setup with sample data | [Docker quick start](#docker-default) |
| No Docker on macOS | [Native macOS](NATIVE_MACOS.md), then [shared native setup](NATIVE_COMMON.md) |
| No Docker on Ubuntu 24.04 LTS | [Native Ubuntu](NATIVE_UBUNTU.md), then [shared native setup](NATIVE_COMMON.md) |
| VS Code manages the container environment | [Dev Container](DEV_CONTAINER.md) |

The native sample recipes have passed clean Ubuntu 24.04 ARM64 and Apple Silicon
macOS walkthroughs; the actual VS Code walkthrough passed on Apple Silicon.
Other architectures, real WSL2 ownership/networking and hosted Codespaces have
not been rehearsed. Codespaces also needs development host/CSRF work; it is not
a ready-to-use hosted option. See [Dev Container limits](DEV_CONTAINER.md#codespaces-and-remaining-limits).

Use Python 3.13 and the [supported version contract](SUPPORTED_VERSIONS.md).
Docker supplies MySQL 8.0; the native guides use their verified platform packages
within the MySQL 8.0-or-newer contract. Elasticsearch and integrations are opt-in.

## Docker (default)

Install [Docker with Compose](https://docs.docker.com/compose/install/) and start
it. In a directory for a new checkout, run:

```bash
git clone --branch beta https://github.com/GrandComicsDatabase/gcd-django.git
cd gcd-django
./bin/dev setup
```

For a fresh environment, no `.env` or custom Django settings file is required.
Use `./bin/dev up` for later starts without refreshing the sample. Do not clone
over existing work. A new checkout alone does not isolate Docker data: ordinary
Compose uses the same default project name across checkouts. If another GCD
stack exists, select a distinct `COMPOSE_PROJECT_NAME` and unused host ports in
the new checkout's `.env` before running any command, and retain those settings.
The editor workflow has its own [isolation rules](DEV_CONTAINER.md#isolation-and-existing-databases).

With default ports, the application is available at <http://127.0.0.1:8000>.
MySQL is available only on `127.0.0.1:3308` from the local machine. Database data
lives in the Docker volume named `gcd-django-dev_mysql_data` with the default
project name.
Keep the environment local; its fixture credentials are public.

Confirm it works, then log in with a sample account below. If you selected other
ports, substitute them in the URLs and checks; querying port 8000 could otherwise
reach an older environment rather than this checkout's service:

```bash
./bin/dev doctor
curl --fail --silent --show-error http://127.0.0.1:8000/health/
./bin/dev test apps/gcd/tests/test_health.py -q
```

A successful health request does not by itself verify editing or approval.
For failures, start with [troubleshooting](TROUBLESHOOTING.md), not a database reset.

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

In the Docker runtime, setup can replace existing data after confirmation.
Replacement removes the selected project's MySQL, Elasticsearch and Redis
volumes, not just sample rows. Review the project and preserve local work before
accepting; do not add `--replace --yes` to bypass a prompt without that review.
Native setup instead seeds in place as described in the shared native guide.

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
fixtures. Keywords of catalog records are copied and linked to the local
content types.

#### MySQL memory for the full catalog

The full catalog is larger than 7 GiB, so MySQL's default 128 MiB InnoDB
buffer pool leaves relatively little catalog data cached. A local full-dump
comparison found that a 1 GiB buffer pool reduced physical reads and improved
cold-query performance, although already-warm scan times were similar. A 1 GiB
buffer pool is therefore the recommended starting point for both Docker and
native development setups. This is a local-development recommendation, not a
production configuration.

##### Docker

The Docker setup configures a 1 GiB buffer pool automatically. To use less
memory on a constrained machine, copy `.env.example` to `.env` only if `.env`
does not exist, then edit the existing file to set a lower value:

```dotenv
GCD_MYSQL_BUFFER_POOL_SIZE=512M
```

Restart the Docker stack after changing the value:

```bash
./bin/dev down
./bin/dev up
```

A smaller buffer pool uses less memory but can make full-catalog imports and
queries slower.

##### Native

For a native installation, configure the same setting in the MySQL server's
option file:

```ini
[mysqld]
innodb_buffer_pool_size=1G
```

Restart MySQL after changing its option file. File locations and service
commands differ by operating system and package manager. The
`GCD_MYSQL_BUFFER_POOL_SIZE` environment variable configures only the Docker
service; it does not change a native MySQL installation.

The [macOS](NATIVE_MACOS.md#2-start-and-configure-local-mysql) and
[Ubuntu](NATIVE_UBUNTU.md#3-configure-local-mysql) guides show the
platform-specific option files, backups and readiness checks for dedicated
local servers.

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
optional extension of the Docker core environment. For the first search-enabled
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

Public-dump indexing requires valid catalog relationships. Older snapshots can
contain references to missing creators or universes and stop a rebuild. If that
happens, report the error and affected record IDs and use a dump confirmed to
contain the corrections, or use the deterministic sample dataset. Rebuilding
does not repair the database or silently skip broken relationships.

After an index exists, preserve and reuse it with:

```bash
./bin/dev search-up
```

Search data and queued jobs live in Docker volumes and survive normal
`./bin/dev down` / `search-up` cycles. The normal `./bin/dev up` command keeps
search disabled and does not start Elasticsearch, Redis, or the worker.

To change local ports or other development-only settings, including the
Elasticsearch host port and MySQL buffer-pool size, copy `.env.example` to
`.env` only if it does not exist; otherwise edit the existing file. Use literal
`KEY=VALUE` entries. Shell expressions are deliberately
not evaluated. Do not use production credentials in this file.

`./bin/dev reset --yes` removes the local Docker database, Elasticsearch, and
Redis volumes and starts a fresh core database. It is intentionally
confirmation-gated.

## Native (Docker-free)

For a new installation, follow [macOS](NATIVE_MACOS.md) or
[Ubuntu 24.04](NATIVE_UBUNTU.md), then [shared native setup](NATIVE_COMMON.md).
The guides cover build tools, a separate Python 3.13 virtualenv, a local MySQL
server, database/test-schema grants, connection settings and sample logins.
Docker is not required.

Once those prerequisites and the repository-root `.env` are ready:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native setup
```

Native setup applies migrations, seeds the sample and fixture accounts, checks
the environment and runs Django in the foreground. It accepts no options and
only permits Django's selected database to be named `gcd_dev`, `gcd_django_dev`,
or `gcd_dev_*` with a lowercase letter/digit/underscore suffix. It does not
create the database or require MySQL root credentials. A name guard does not
replace verifying the connection destination.

Repeating native setup refreshes sample data, fixture accounts and global
statistics without dropping or flushing the database; unrelated catalog data
remains. Use daily `up` when you do not intend to reseed:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native up
```

Leave the foreground server running and use a second terminal for checks:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native doctor
PYTHON=.venv/bin/python ./bin/dev --runtime native test apps/gcd/tests/test_health.py -q
```

Ctrl-C stops Django, not MySQL. Native MySQL normally uses port 3306; configure
`MYSQL_PORT=3306` explicitly in `.env`, since the launcher otherwise falls
back to the Docker host port 3308. Native setup disables search even if the
calling shell enabled it. Full-dump import and managed search remain Docker-only.

Native `reset --yes` flushes local edits and reapplies migrations, and only
permits `gcd_dev` or `gcd_django_dev`. It is not a stop command or a
troubleshooting shortcut. See [daily use and preservation](NATIVE_COMMON.md#daily-use-and-preservation).
