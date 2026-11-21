# Development on Windows with WSL2

Use Ubuntu 24.04 under Windows Subsystem for Linux 2. Direct native Windows
Python/MySQL installation is not a supported development path. Choose one
runtime and keep its tools and data separate:

| Choice | Where Python and MySQL run | Continue with |
| --- | --- | --- |
| No Docker | Inside Ubuntu, managed as native Linux services | [Native setup](#3a-native-ubuntu-without-docker) |
| Docker Desktop | In Linux containers, accessed from Ubuntu | [Docker setup](#3b-docker-desktop-alternative) |

The native sample-data walkthrough passed on Ubuntu 24.04.5 x86_64 under WSL2,
with Python 3.13.18 and MySQL 8.0.46. It covered tests, Windows-browser login,
sample create/edit/approval, Linux-owned file saves and autoreload, repeat setup,
MySQL restart, and WSL distro stop/reopen persistence. It used a pinned source
archive, not a fresh Git clone. Docker Desktop and VS Code's WSL/Dev Container
integration have not yet been validated by this walkthrough; they are separate
from native runtime and file-ownership results. Codespaces is deferred to a
separate follow-up. See the [environment chooser](CORE_SETUP.md).

## 1. Prepare Ubuntu 24.04 under WSL2

Use a Windows installation that meets Microsoft's current
[WSL prerequisites](https://learn.microsoft.com/en-us/windows/wsl/install).
Before enabling Windows features, updating WSL or restarting Windows, inspect
existing distributions and preserve any running work. Do not unregister a
distribution, reset Docker or change the default distribution to troubleshoot
this setup. A Windows VM also needs working nested virtualization; a running
Windows desktop alone does not prove WSL2 can start.

In **Windows PowerShell**, inspect the WSL release and distributions:

```powershell
wsl --version
wsl --list --verbose
```

If WSL is absent or too old, follow Microsoft's installation/update instructions.
If Ubuntu 24.04 is missing, open **PowerShell as administrator** and run:

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
```

Confirm that exact distribution name is available before installing. Do not
silently choose a different Ubuntu release. Restart Windows if the installer
requires it, after saving other work. Open Ubuntu and create an ordinary Linux
user account. In PowerShell, `wsl --list --verbose` must show Ubuntu-24.04 with
version `2`. For an existing WSL1 installation, review Microsoft's conversion
instructions and preserve its data before converting it.

In the **Ubuntu terminal**, check:

```bash
cat /etc/os-release
ps -p 1 -o comm=
```

Expect Ubuntu 24.04 and `systemd` as PID 1. If systemd is absent, follow
[Microsoft's systemd guidance](https://learn.microsoft.com/en-us/windows/wsl/systemd)
while retaining existing `/etc/wsl.conf` settings. Do not repeatedly run failing
`systemctl` commands or reinstall MySQL. Any required WSL shutdown interrupts
Linux processes, including other projects; stop those deliberately first.

## 2. Keep project files in Ubuntu

Use the **Linux filesystem**, such as `~/Code/gcd-django`, for the checkout and
its `.venv`, not `/mnt/c/Users/...`. Do not reuse a Windows-created virtualenv.
This avoids cross-filesystem performance and permission differences; see
[Microsoft's filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).

Clone the repository once, as directed by the chosen setup guide below, from
a parent directory inside the Linux filesystem. For normal development use
`beta`, or the review branch specified by a maintainer. Do not clone over
existing work. If using VS Code, open the folder through its WSL connection
so the editor and terminal use the same Linux tools; that editor integration
is distinct from the completed native walkthrough.

## 3A. Native Ubuntu without Docker

In the **Ubuntu terminal**, follow [Native Ubuntu 24.04](NATIVE_UBUNTU.md), then
[Shared native setup](NATIVE_COMMON.md). They install Linux build dependencies,
Python 3.13 and MySQL, clone the repository, create a normal `.venv`, and
provision a dedicated database and non-root application/test account.

Docker Desktop is not required for this choice. After those prerequisites,
the single sample-setup command is:

```bash
PYTHON=.venv/bin/python ./bin/dev --runtime native setup
```

Use the native guide's `.env`, including `MYSQL_PORT=3306` for its local server.
The launcher's default port 3308 is for a Docker-managed database accessed from
the host; it is not the native MySQL default. Keep MySQL bound to loopback.

The setup command runs Django in the foreground. Keep that terminal open;
use a second Ubuntu terminal in the same checkout for checks and tests.
After MySQL installation, verify readiness before provisioning data:

```bash
systemctl is-active mysql
sudo mysql
```

Exit the MySQL prompt after confirming the dedicated server accepts connections.
After the scoped application account exists, use the shared guide's TCP check
instead. The native recipe handles sample data, not full-dump imports or native
Elasticsearch/Redis management; those remain separate Docker workflows.

## 3B. Docker Desktop alternative

This route is documented for contributors who already prefer Docker, but its
Windows/WSL integration has not yet been validated by the GCD walkthrough.
Check [Docker's current Windows/WSL prerequisites](https://docs.docker.com/desktop/features/wsl/)
before installing or changing an existing Docker environment.

1. Install/start Docker Desktop for Windows with the WSL2 backend and Linux
   containers.
2. Enable Ubuntu-24.04 in **Settings > Resources > WSL Integration**.
3. Do not install a second Docker Engine inside Ubuntu for this route. If one
   already exists, preserve its data and review Docker's migration instructions
   before removing or changing anything.

In the **Ubuntu terminal**, verify engine access and Compose:

```bash
docker version
docker compose version
```

Then follow [Docker core setup](CORE_SETUP.md#docker-default), cloning into the
Linux filesystem. Its initial sample command is `./bin/dev setup`; later starts
use `./bin/dev up`. Native Python/MySQL installation is not required for this
choice. A second checkout alone does not isolate ordinary Compose data: select
a distinct project name and unused ports if another GCD environment exists.
Review any replacement prompt before accepting it; it can remove that project's
database, search and queue volumes. For editor-managed containers, read the
[Dev Container guide](DEV_CONTAINER.md) and its current platform limitations.

## 4. Verify the application and daily workflow

Wait for Django's server-ready message, then check the selected web port from
Ubuntu. These examples use port 8000; substitute your configured `GCD_WEB_PORT`
everywhere if it differs:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/health/
```

Open `http://localhost:8000` in the **Windows browser**, log in with a
[sample account](CORE_SETUP.md#ready-to-use-development-data), and find the
`[GCD DEV]` catalog. Exercise the sample editing workflow, not just health.
For native development, run the shared guide's doctor and focused tests in
the second Ubuntu terminal. For Docker, use the core guide's commands.

Windows can reach Linux applications using localhost under the documented
[WSL networking behavior](https://learn.microsoft.com/en-us/windows/wsl/networking).
If the Ubuntu health check passes but Windows cannot connect, confirm both
checks use the selected port, check for another Windows listener, and review
WSL networking and applicable VPN/firewall policies. Do not disable the firewall
or publish MySQL to the network as a workaround.

Ctrl-C stops native Django without deleting data; MySQL is a separate service
and may remain running after its terminal closes. Terminating the distribution
stops its Linux processes. Before an intentional distro restart, save editor
changes and stop the selected development server
and database gracefully. Reopen Ubuntu, confirm MySQL readiness, and start
Django again. Do not use a global WSL shutdown to stop one development server.
See [shared daily commands](NATIVE_COMMON.md#daily-use-and-preservation) and
[troubleshooting](TROUBLESHOOTING.md).
