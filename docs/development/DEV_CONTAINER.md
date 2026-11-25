# VS Code Dev Container

The Dev Container uses the repository's existing Docker Compose application,
MySQL service and Python image. It adds an editor environment with sample data;
it does not require Python, Node.js or MySQL to be installed on your host.

This is the local Phase 5 implementation. The actual VS Code editor walkthrough
has passed on Apple Silicon macOS, including file saves, tests, forwarded login
and rebuild persistence. Actual Dev Container CLI lifecycle checks also passed
on Apple Silicon Docker Desktop and Linux x86_64, including non-root file writes,
sample login, tests, reopen/recreate persistence and scoped stop. The Linux run
verified host/bind ownership at UID 1000, not remapping from another UID.
Linux/WSL2 VS Code GUI integration and Intel macOS remain unverified.
Codespaces is deferred to a separate follow-up.
For the established command-line Docker workflow, use [Core setup](CORE_SETUP.md).

## Prerequisites

- VS Code and its **Dev Containers** extension.
- A running Docker installation with Docker Compose **2.24.4 or newer**.
- Git and Bash on the host where the checkout is opened: macOS, Linux, or a
  WSL2 Linux distribution. Direct native Windows shells are not this path.
- A local clone of this repository. For WSL2, keep it in the Linux filesystem
  rather than under `/mnt/c` and open it through VS Code's WSL integration.

The Compose version can be checked with `docker compose version`. The editor
override clears inherited host port mappings using Compose's
[`!reset` merge behavior](https://docs.docker.com/reference/compose-file/merge/#reset-value).
If startup reports `additional privileges requested` for a generated
`Dockerfile-with-features`, check the
[Compose/Buildx compatibility note](TROUBLESHOOTING.md#editor-containers-and-unverified-platforms)
before changing permissions.

## Open the environment

1. Open the repository folder in VS Code. A fresh clone needs no `.env` file;
   the default credentials are public local-development fixtures, not production
   secrets.
2. Run **Dev Containers: Reopen in Container** from the Command Palette.
3. Wait for container creation, migrations and post-create setup to finish.
   In the **Ports** panel, open the forwarded **GCD** port, `8000`. Check
   `/health/` before using the application if the server is still starting.

This uses the standard VS Code
[Reopen in Container workflow](https://code.visualstudio.com/docs/devcontainers/create-dev-container).
The editor opens `/workspace` as the non-root `gcd` user, with Python and
Pylance extensions and `/usr/local/bin/python` selected. On Linux, the Dev
Containers integration is configured to align the editor user's UID with the
local user. The Linux CLI check confirmed writable files owned by the host's
UID 1000. Non-1000 UID remapping and WSL2 Dev Container editor ownership have
not yet been verified.

Startup waits for MySQL health and successful migrations. The finite post-create
hook then runs `seed_development_data` and the environment doctor. Django remains
the existing Compose `web` service, not a background process launched by an
editor hook. No manual migration, fixture-loading or second server command is
needed.

The sample contains the `[GCD DEV]` catalog, dummy images and these local logins:

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin` | Local administrator |
| `editor` | `editme` | Editor and indexer |
| `dexter_1234` | `test` | Indexer |

These accounts belong only to the sample environment. They do not authenticate
against beta or production. Email is written to the console and Elasticsearch
is disabled for this path.

## Isolation and existing databases

The host initialization hook derives a Compose project name from the checkout's
canonical path and writes it to the ignored
`.devcontainer/compose.project.yaml`. Its name begins with `gcd-editor-`.
The same path produces the same project; a different or moved checkout produces
a different project and separate named volumes. Moving a checkout does not move
or delete the earlier project's database. Do not edit or commit the generated
file.

Initialization refuses a `COMPOSE_PROJECT_NAME` override from the launching
shell or the repository's root `.env`. This prevents the editor from silently
attaching to an ordinary Compose database. In particular, copying `.env.example`
unchanged introduces its `COMPOSE_PROJECT_NAME=gcd-django-dev` entry.

If this guard stops startup, unset that variable in the environment launching
VS Code. Remove the `.env` entry only when deliberately preparing that checkout
for this new editor path. If the checkout already manages a database you want
to preserve, use a fresh clone instead of changing its existing configuration.
Never reset or delete an existing database to resolve this guard. The hook
checks configuration without starting services and does not rewrite `.env`.

Neither MySQL nor Django is published directly on a host Docker port in this
configuration. The editor forwards only application port `8000`; use the local
address shown in its Ports panel, which can differ when that host port is busy.
MySQL remains reachable internally as `db:3306`. Do not forward its port.

## Commands inside the editor

Use the integrated terminal, which already has the container's Python and
`settings_dev` environment:

```bash
python scripts/check_dev_environment.py
python manage.py check
python manage.py migrate --check
python -m pytest apps/gcd/tests/test_health.py apps/gcd/tests/test_seed_development_data.py -q
```

Run other application tests with `python -m pytest PATH_TO_TESTS`. The database
first-initialization hook gives the application account privileges only on the
exact development schema and its `test_` counterpart, allowing pytest to create
and remove its test database, and `SELECT` on the two Performance Schema tables
`data_locks` and `data_lock_waits`, which the tests of concurrent changes read.
It does not give the editor global MySQL privileges
or root credentials. This hook runs in the database container on a new volume,
not in an already-populated database. An unexpected test-database permission
error should be investigated; it is not a reason to grant global privileges or
reset a preserved volume.

There is no Docker socket or Docker-in-Docker service in the editor container.
Use Python commands there, not the Docker-backed `./bin/dev` commands. Manage
the container lifecycle through VS Code on the host.

## Reopen, rebuild and stop

Reopening the same checkout reuses its database volume. After changing the
image or container configuration, use **Dev Containers: Rebuild Container**.
Container recreation can rerun the sample seeder: it refreshes fixture accounts
and the marked sample records without dropping the database or removing unrelated
catalog data. A rebuild is not a database reset.

The configuration sets `shutdownAction` to `stopCompose`: closing the editor
connection stops this Compose project while retaining named volumes. Do not use
volume-deleting cleanup commands as a routine stop or troubleshooting step.
Reopen/rebuild/close, extension permissions and GUI file saves have been checked
in the Apple Silicon macOS walkthrough. The Linux CLI rehearsal separately
verified UID-1000 file ownership, reopen/recreate persistence and scoped stop;
it did not exercise VS Code GUI forwarding or WSL2 editor integration.

## Codespaces and remaining limits

Codespaces is deferred to a separate follow-up and is not supported by this
local setup. Do not treat the configuration as a validated hosted environment.
The follow-up must implement and test the hosted path; a real rehearsal requires approval
for any billable resources and a cleanup plan. It must use sample data only,
with port `8000` kept **private** and no forwarded database port. GitHub documents
how [forwarded port visibility works](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace).

There is also a known application-host gap: `settings_dev.py` currently allows
only localhost addresses, not a Codespaces `*.app.github.dev` hostname. Hosted
browser access, login and CSRF behavior need a narrowly scoped development-only
implementation and real testing. Do not work around this with wildcard host or
origin trust, or by exposing the sample environment publicly.

This editor path does not import the authenticated public dump or enable the
optional search stack. Use the separate Docker workflows in
[Core setup](CORE_SETUP.md) for those tasks. For Docker-free development, use
[native macOS](NATIVE_MACOS.md), [native Ubuntu](NATIVE_UBUNTU.md), or
[Windows with WSL2](WSL2.md), then
[shared native setup](NATIVE_COMMON.md). Those workflows install Python and
MySQL directly on the host and are separate from this container configuration.
See [troubleshooting](TROUBLESHOOTING.md) for runtime-specific diagnostics.
