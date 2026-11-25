# Shared native setup and daily use

Start with [native macOS](NATIVE_MACOS.md), [native Ubuntu 24.04](NATIVE_UBUNTU.md),
or [Windows with WSL2](WSL2.md).
This page assumes Python 3.13, the platform build dependencies, a running local
MySQL server, a new checkout, and its `.venv` already exist. Docker is not required.

The core sample workflow has been rehearsed on Ubuntu 24.04 ARM64, Apple Silicon
macOS, and Ubuntu 24.04 x86_64 under WSL2. The WSL2 run used a pinned source
archive; it verified native runtime behavior, not Docker Desktop or editor
integration. Full-dump imports and managed search are separate
[Docker workflows](CORE_SETUP.md); these native instructions do not implement them.

## 1. Install Python dependencies

From the repository root, in the terminal prepared by the platform guide:

```bash
.venv/bin/python -m pip install --upgrade pip 'setuptools<81'
.venv/bin/python -m pip install -r requirements.txt
```

Keep the compatibility constraint and use the repository's requirements, not
system Python or `sudo pip`. On macOS, retain the platform guide's
`PKG_CONFIG_PATH` while building dependencies. See [supported versions](SUPPORTED_VERSIONS.md).

## 2. Create a dedicated local database and account

This is a one-time administrator step on your local MySQL server. Never point
it at beta, production, or another person's database. The application and tests
will use a separate, restricted account afterward.

| Platform | Open the MySQL administrator prompt |
| --- | --- |
| New Homebrew MySQL after securing the root account | `mysql -u root -p` |
| Ubuntu's default local socket-authenticated root account | `sudo mysql` |

After starting or restarting MySQL, wait for this connection to succeed. A
service-manager success message does not prove database readiness. If refusal
persists, inspect the service rather than resetting data or credentials.

At the `mysql>` prompt, confirm the server and check for name collisions:

```sql
SELECT @@hostname, @@port, VERSION(), @@GLOBAL.partial_revokes;
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME IN ('gcd_dev', 'test_gcd_dev');
SELECT User, Host FROM mysql.user WHERE User = 'gcd_dev';
```

Continue only if you recognize the dedicated local server, both collision
queries return empty sets, and all queries succeeded. An existing account at
any host is a reason to stop and review. Do not drop it, change its password,
or use `IF NOT EXISTS` to skip these checks.

For a fresh server with `partial_revokes=0`, run:

```sql
CREATE DATABASE gcd_dev CHARACTER SET utf8mb4;
CREATE USER 'gcd_dev'@'127.0.0.1' IDENTIFIED BY 'gcd_dev_password';
GRANT ALL PRIVILEGES ON `gcd\_dev`.* TO 'gcd_dev'@'127.0.0.1';
GRANT ALL PRIVILEGES ON `test\_gcd\_dev`.* TO 'gcd_dev'@'127.0.0.1';
SHOW GRANTS FOR 'gcd_dev'@'127.0.0.1';
EXIT;
```

The escaped underscores make these exact database grants under MySQL's default
rules, not wildcard patterns. If `partial_revokes=1`, use `gcd_dev` and
`test_gcd_dev` without backslashes in the two grants. Do not change the server's
setting to follow the guide. See [MySQL database-level grants](https://dev.mysql.com/doc/refman/8.4/en/grant.html).

There are no global privileges, grant option, or remote-host account. Django
creates and removes `test_gcd_dev` when running database tests; never store
valuable data there. Run tests without parallel workers, which require additional
database names not covered by these grants.

`gcd_dev_password` is a public local-development default. If your server's
password policy rejects it, choose a unique development password and put the
same value in `.env` below. Do not weaken the policy, publish private passwords,
or put them in shell command arguments.

## 3. Save the connection settings

Create `.env` in the repository root with your editor. If it already exists,
review it and edit only the intended values rather than replacing it:

```dotenv
MYSQL_DATABASE=gcd_dev
MYSQL_USER=gcd_dev
MYSQL_PASSWORD=gcd_dev_password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
GCD_WEB_PORT=8000
```

Use literal `KEY=VALUE` entries, without quotes, shell expansion, or `export`.
The file is ignored by Git and must not be committed. `PYTHON` and
`PKG_CONFIG_PATH` are not supported `.env` keys; set them in the shell instead.
Exported shell variables take precedence over `.env`, so check for stale
connection settings from another project if the destination is unexpected.

Explicit `MYSQL_PORT=3306` matters: the launcher otherwise falls back to the
Docker host port, normally **3308**. With the settings above, check the
application account using a password prompt:

```bash
mysql --protocol=TCP -h 127.0.0.1 -P 3306 -u gcd_dev -p gcd_dev -e 'SELECT VERSION(), DATABASE(), CURRENT_USER(), @@innodb_buffer_pool_size;'
```

Adjust this diagnostic if you deliberately chose another host, port or database.
A 1 GiB buffer pool reports `1073741824` bytes; `512M` reports `536870912`.
Configure native MySQL through its option file as described by the platform
guide. `GCD_MYSQL_BUFFER_POOL_SIZE` controls only the Docker service.

## 4. Start the sample environment

After the one-time prerequisites and provisioning, run:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native setup
```

This applies migrations, seeds sample records and local accounts, checks the
environment, and runs Django in the foreground. It does not create the MySQL
database or require administrator credentials. It accepts no options and
requires Django's selected database name to be `gcd_dev`, `gcd_django_dev`, or
`gcd_dev_*` with a lowercase letter/digit/underscore suffix. This name check
does not establish that a server is local or safe; verify the connection first.

The sample reserves user IDs 1–4 for `admin`, `editor`, `dexter_1234` and `anon`.
Setup refuses to load its account fixture if one of those IDs belongs to a
different username, or a sample username belongs to another ID. Existing sample
identities can be refreshed normally. The fixture also reserves profile and
collector IDs 1–4 and collection IDs 1–4 and 101–104. Setup refuses to reassign
those rows to different owners, even if the existing user's ID is not reserved.
It also refuses a sample user's profile or collector at a different ID, instead
of creating a conflicting one-to-one record. The fixture reserves group IDs
1–5 for `editor`, `indexer`, `admin`, `member` and `board`, membership row IDs
1–6, and group-permission row IDs 1–9. Setup checks group IDs/names and both
association endpoints before loading. It refuses mismatched rows or a sample
group name or association pair at a different ID. Permission identities are
matched by codename, app and model, not database-specific numeric IDs.
Unrelated collections, groups and associations outside these reservations are
retained. On a conflict, preserve the database and use a separate empty
development database; do not delete or rename accounts, groups or associations
to bypass the guard.

Wait for Django's `Starting development server at http://127.0.0.1:8000/`
line and a successful health response before opening the site. The earlier
`GCD is available at ...` message announces the intended address before Django
finishes starting. Keep the process running; use another terminal for checks.
If you selected a different web port, use that port throughout.

Open [the local site](http://127.0.0.1:8000/) and sign in:

| Username | Password | Use |
| --- | --- | --- |
| `admin` | `admin` | Local administrator and approval testing |
| `editor` | `editme` | Local editor/indexer workflow |
| `dexter_1234` | `test` | Local indexer |

These public fixture credentials do not authenticate against comics.org or
beta.comics.org. Keep this environment on loopback and never expose it publicly.
The `anon` fixture supports anonymous behavior and cannot log in.

## 5. Confirm the installation

In a second terminal at the repository root:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native doctor
curl --fail --silent --show-error http://127.0.0.1:8000/health/
PYTHON=.venv/bin/python ./bin/dev --runtime native test apps/gcd/tests/test_health.py -q
```

Expect supported versions, successful database checks, HTTP 200 with
`{"status": "ok"}`, and passing tests. The first database-test run creates and
migrates a disposable test database, so it can take longer than a page request.
Also log in, find `[GCD DEV]` records, and exercise the sample edit/approval
workflow relevant to your task. Health alone does not test that workflow.

For failures, use [troubleshooting](TROUBLESHOOTING.md). Do not reset the database
as a first response.

## Daily use and preservation

Start without refreshing sample data:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native up
```

Other useful commands, using the same `.env`:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native manage check
PYTHON=.venv/bin/python ./bin/dev --runtime native manage showmigrations
PYTHON=.venv/bin/python ./bin/dev --runtime native shell
```

Ctrl-C stops Django, not MySQL. No virtualenv activation is needed when using
the explicit interpreter path. Native `setup` resolves a relative `PYTHON`
path from the repository root; running these commands there also keeps daily
operations unambiguous.

Repeating `setup` refreshes the sample, fixture accounts and global statistics
without dropping or flushing the database. Unrelated catalog records remain,
but this is neither a backup nor a production-data workflow. Native setup
disables Elasticsearch, even if the calling shell enabled it. Use daily `up`
when you do not intend to reseed.

Native `reset --yes` is different: it flushes the selected database, including
local edits, checks migrations and restores the initial reference tables needed
for the next sample setup. Run `setup` afterward to recreate the sample and
development logins. Reset only permits `gcd_dev` or
`gcd_django_dev`. Use it only after verifying the exact host, port and database,
and confirming all data is disposable or backed up. Stopping the server,
changing branches and resolving dependency errors do not require a reset.

## Hybrid and optional services

Native Python with a Docker-managed MySQL server is a separate hybrid choice,
not the Docker-free recipe above. It requires Docker and client build libraries,
uses the Docker host port (normally 3308), and must retain that Compose project's
credentials and volume. Do not run the native-server provisioning SQL against an
existing Compose database. Native tests also need explicit test-database grants;
the normal Compose-created account is not guaranteed to have them.

For full catalog imports or managed Elasticsearch/Redis/workers, use
[Docker core and search](CORE_SETUP.md). Native `setup --dump` is intentionally
rejected; it does not silently switch runtimes.
