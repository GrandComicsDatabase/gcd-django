# Development setup troubleshooting

Start with the [setup chooser](CORE_SETUP.md) and diagnose the environment you
selected. Preserve databases, source archives and local changes. These are
development instructions, not permission to change a shared or production service.

## Identify the runtime

Run Docker commands from the checkout that owns the intended Compose project:

```bash
docker compose ps -a
./bin/dev doctor
docker compose logs --tail=80 db migrate web
```

For native development, use that checkout's configured `.env` without overriding
a deliberate custom database port:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native doctor
PYTHON=.venv/bin/python ./bin/dev --runtime native manage check
```

Inside a [Dev Container](DEV_CONTAINER.md), use its integrated terminal:

```bash
python scripts/check_dev_environment.py
python manage.py check
```

The editor has no Docker socket. Host Docker commands belong on the host.
Doctor checks configuration, versions and connectivity; it does not prove
that the browser or sample editing workflow works.

## Python and dependency installation

| Symptom | Check and next action |
| --- | --- |
| Native launcher rejects Python | Check `.venv/bin/python --version`; the project requires Python 3.13. Preserve local environment notes before recreating a disposable virtualenv. Do not replace system Python. |
| Ubuntu supplies another Python version | Follow [native Ubuntu](NATIVE_UBUNTU.md) for a separate interpreter, not a system-Python upgrade. |
| PyICU will not build | Check compiler tools and ICU development libraries. On macOS, use the guide's `PKG_CONFIG_PATH` in the pip-install terminal. Do not guess `ICU_VERSION`. |
| `mysqlclient` will not build | Check MySQL client headers and pkg-config metadata; a running database alone does not supply the build dependencies. |
| `pkg_resources` or setuptools failure | Retain the documented `setuptools<81` bootstrap. Do not unpin unrelated requirements to hide the error. |
| Works in only one terminal | Compare the interpreter, exported connection settings and build-library paths. `.env` neither activates Python nor executes shell commands. |

Useful native read-only checks:

```bash
.venv/bin/python --version
.venv/bin/python -m pip check
pkg-config --modversion icu-i18n
pkg-config --modversion mysqlclient
```

The pkg-config checks require the platform guide's library paths. For missing
or retired packages, check [supported versions](SUPPORTED_VERSIONS.md) and ask
for help rather than choosing an untested Python major/minor version.

## MySQL connections and permissions

| Symptom | Check and next action |
| --- | --- |
| Connection refused | Check service readiness and the selected port: native normally 3306, Docker from host 3308, Docker from web `db:3306`. A service-start message can precede readiness. |
| Access denied | Check the username and account host. Native TCP to `127.0.0.1` differs from an administrative socket login. Do not change another environment's account. |
| Unknown database | Complete [native provisioning](NATIVE_COMMON.md#2-create-a-dedicated-local-database-and-account). Migrations create tables, not the MySQL database. |
| Site works but pytest cannot create its database | Verify exact test-schema grants, including underscore escaping and `partial_revokes`, in the shared guide. Do not run the application as root or grant global privileges. |
| Unsupported MySQL version | Inspect `SELECT VERSION()` on the server; `mysql --version` reports the client. |
| Buffer-pool change has no effect | Verify the effective value after restart. `GCD_MYSQL_BUFFER_POOL_SIZE` controls Docker startup, not native MySQL. |

For the shared native guide's defaults, open a password-prompted connection:

```bash
mysql --protocol=TCP -h 127.0.0.1 -P 3306 -u gcd_dev -p gcd_dev
```

Adjust those values for an intentionally different local server. Then inspect:

```sql
SELECT VERSION(), DATABASE(), CURRENT_USER();
SHOW GRANTS;
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
```

The 1 GiB buffer pool reports `1073741824` bytes. These queries do not change
data. Do not post passwords, full environment dumps, or private catalog data.

## Startup and the browser

- **Port 8000 is occupied:** identify the listener before stopping anything.
  Set an unused `GCD_WEB_PORT` for ordinary Docker/native setup and use it in
  the browser and checks. For Dev Containers, use the forwarded address shown
  in the Ports panel. Do not stop an unrelated project.
- **A command succeeds but the site is unavailable:** inspect web and migration
  logs. A running database or successful doctor is not a listening web server.
  Native setup's early URL announcement also precedes Django readiness; wait
  for its server-start line and a successful `/health/` response.
- **The native server exits when its terminal closes:** `up` and `setup` run
  in the foreground. Keep that terminal open and use another for tests.
- **Health returns 503:** inspect database errors and connection settings. Do
  not extend a timeout to hide a failed database connection.
- **Health passes but sample login or editing fails:** confirm `setup` completed
  and use the documented local accounts and `[GCD DEV]` records. `up` alone does
  not seed. A full catalog dump does not include complete editable history.
- **Native setup rejects options:** native sample setup accepts none. Full
  dumps and managed search use the Docker workflow, not native flags.
- **`.env` is rejected:** use allowlisted literal `KEY=VALUE` entries. Keep
  `PYTHON`, `PKG_CONFIG_PATH`, shell expansion and arbitrary Django settings out.
- **Old `settings_local.py` changes behavior:** reproduce in a separate clean
  clone. Preserve that file for its original environment instead of deleting it.
- **Startup reports partially initialized `markdown.treeprocessors`:** preserve
  the traceback and Git commit. The current code initializes the parent Markdown
  package before its submodules and includes a cold-import regression test.
  Do not disable autoreload or bypass sanitization to hide a startup failure.

## Editor containers and unverified platforms

- Workspace Trust should apply only to the checkout whose container scripts
  you reviewed, not its parent directories.
- A permission failure needs correct non-root identity, home and workspace
  ownership. Do not use recursive `chmod 777` or run the editor application as root.
- A `COMPOSE_PROJECT_NAME` refusal is an isolation guard. Follow the
  [Dev Container guide](DEV_CONTAINER.md#isolation-and-existing-databases);
  do not reset a preserved database to bypass it.
- **`additional privileges requested` for `Dockerfile-with-features`:**
  Compose 5.6.1 with newer Buildx can omit the read grant for the temporary
  Dockerfile generated by Dev Containers. Docker fixed this in
  [Compose 5.7.0](https://github.com/docker/compose/releases/tag/v5.7.0).
  Update Compose or Docker Desktop to a release containing that fix. It grants
  access to the configured build inputs without disabling filesystem checks.
  Do not grant access to the whole filesystem or set
  `BUILDX_BAKE_ENTITLEMENTS_FS=0` to bypass the error.
- Rebuild is not reset. The same editor checkout retains its database volume.
  Closing VS Code stops its project after the extension's shutdown delay.
  Check the logs before treating exit 137 as OOM; the tested extension uses
  a zero-second stop timeout and Docker reported `OOMKilled=false`.
- Native WSL2 sample setup, Linux file ownership and Windows-browser access
  passed their walkthrough. Docker Desktop/WSL editor integration is a separate
  coverage gap; see [WSL2](WSL2.md). Codespaces is deferred, and its host/CSRF
  support remains unfinished. Do not expose sample
  credentials publicly, enable wildcard hosts, or disable CSRF to work around it.

## Full dumps and search

Use [Docker import/search](CORE_SETUP.md) and check Docker storage as well as
host free space before a large import. Keep the downloaded archive separately.
Real uploaded covers and complete editorial history are absent from the public
dump; dummy images and sample records support local workflow checks.

For broken creator/universe references during indexing, preserve the exception,
record IDs, snapshot identity and current progress. Ask for a corrected dump.
Do not patch the preserved archive, silently skip records or automatically
restart a long rebuild. A historical benchmark does not validate a new snapshot.

## Ask for help

Include the guide, OS/architecture, Git commit, runtime versions, exact command,
redacted error and whether the data came from the sample or a dump. Mention
nondefault ports and what passed before the failure, without exposing credentials.
Stopping preserves data. Resetting or deleting volumes is a separate destructive
choice for an explicitly disposable environment, never the first diagnostic step.
