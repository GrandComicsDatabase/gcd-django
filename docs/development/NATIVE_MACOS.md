# Native development on macOS

Docker is not required for this path. Python, MySQL and Django run directly
on your Mac. After the one-time prerequisites, the native setup command
applies migrations, adds sample data, checks the environment and starts the
site. For other choices, see [Core setup](CORE_SETUP.md).

The clean sample-data walkthrough passed on **Apple Silicon macOS 26.6.2**
with Python 3.13.18, MySQL 8.4.13 and Django 5.2.19. It covered dependency
installation, tests, sample login/edit/approval, repeat setup and MySQL restart
persistence. These are measured versions, not a claim that every macOS release
or architecture has been tested. Use the [supported version policy](SUPPORTED_VERSIONS.md)
when selecting packages.

Apple Silicon on macOS 15 or newer is the primary target under
[Homebrew's installation requirements](https://docs.brew.sh/Installation).
The commands derive Homebrew paths instead of assuming an architecture. Intel
macOS has not had a clean walkthrough; Homebrew classifies it as Tier 3, so
this guide does not promise the same package or prebuilt-binary coverage.
Native full-dump import and native search are outside this guide.

## 1. Install the prerequisites

These instructions are for a new, dedicated local development installation.
If MySQL already stores other applications' data, do not replace its server,
reuse its data directory or change its configuration to follow this guide.
Review that installation and choose an isolated development environment first.

Check for the build tools required by native Python extensions:

```bash
xcode-select -p
```

If no developer directory is configured, request the Xcode Command Line Tools:

```bash
xcode-select --install
```

Complete the installer, then confirm that `xcode-select -p` and
`xcrun --find clang` both print a path. If Homebrew is not installed, follow
the [official installation guide](https://docs.brew.sh/Installation), apply
its printed shell setup instructions and open a new terminal.

Before installing MySQL, check for existing server packages, data,
configuration and listeners. A stopped server may still have data at the
path used by Homebrew:

```bash
brew list --formula | grep -E '^(mysql|mariadb|percona-server)(@|$)'
for item in "$(brew --prefix)/var/mysql" "$(brew --prefix)/etc/my.cnf" /etc/my.cnf /etc/mysql/my.cnf; do
  if [ -e "$item" ] || [ -L "$item" ]; then echo "Found: $item"; fi
done
sudo lsof -nP -iTCP:3306 -sTCP:LISTEN
```

On a fresh machine these checks print nothing; no matches from `grep` or
`lsof` is expected. If any check finds a server, data, configuration or a
listener, or you know of a server using a custom path or port, stop and review
it before proceeding. Resolve unexpected command errors rather than treating
them as an empty result. On the clean installation, install the project tools:

```bash
brew install git python@3.13 mysql@8.4 icu4c@78 pkgconf
export PATH="$(brew --prefix mysql@8.4)/bin:$PATH"
export PKG_CONFIG_PATH="$(brew --prefix icu4c@78)/lib/pkgconfig:$(brew --prefix mysql@8.4)/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
```

Select Python 3.13 and MySQL 8.4 explicitly; unversioned formula names may
select another release line. The measured PyICU build used ICU 78.3. The
`icu4c@78` formula is deprecated but available; do not substitute a different
major version without checking the dependency build. See the
[Python](https://formulae.brew.sh/formula/python@3.13),
[MySQL](https://formulae.brew.sh/formula/mysql@8.4) and
[ICU](https://formulae.brew.sh/formula/icu4c@78) formula pages.

The dynamic `PKG_CONFIG_PATH` lets Python packages find the keg-only MySQL
and ICU headers and libraries. Do not set `ICU_VERSION` manually; the build
should discover the installed library. See also
[mysqlclient's Homebrew instructions](https://github.com/PyMySQL/mysqlclient/blob/main/README.md#macos-homebrew).

Keep this terminal open for the remaining steps. For later dependency
reinstalls, repeat the two exports or add them once to your shell's
configuration. They do not belong in the project's `.env`, which accepts
only literal, allowlisted settings. Ordinary use of the installed `.venv`
does not require repeating the package build steps.

## 2. Start and configure local MySQL

Start the new Homebrew server:

```bash
brew services start mysql@8.4
```

Wait for the server to accept connections, then secure its administrator
account using:

```bash
mysql_secure_installation
```

Homebrew initially creates a local root account without a password. Follow
the tool's prompts and keep any root password private; the application will
use a separate account. Do not change an existing server's authentication to
match these instructions. See the [Homebrew MySQL caveats](https://formulae.brew.sh/formula/mysql@8.4).

For this new, dedicated server, back up the Homebrew configuration if it
exists. Keep the printed backup path:

```bash
mysql_config_file="$(brew --prefix)/etc/my.cnf"
if [ -f "$mysql_config_file" ]; then
  mysql_config_backup="$(mktemp "${mysql_config_file}.before-gcd.XXXXXXXX")" &&
    cp -p "$mysql_config_file" "$mysql_config_backup" &&
    printf 'Backup: %s\n' "$mysql_config_backup"
fi
```

If a required backup failed, stop before editing. Otherwise, open
`nano "$mysql_config_file"` in the same terminal. Retain the existing
`[mysqld]` section and unrelated options. Add or update these settings without
adding a second copy of the section:

```ini
[mysqld]
bind-address=127.0.0.1
mysqlx-bind-address=127.0.0.1
innodb_buffer_pool_size=1G
```

Both listeners must remain local. A 1 GiB buffer pool is the recommended
starting point for both Docker and native development; only Docker applies
it automatically. Use `512M` on a memory-constrained machine, leaving room
for MySQL's other allocations, Python and the editor. Native setup does not
edit this file or enforce a buffer-pool value. This is not a production
sizing rule; see [MySQL's buffer-pool documentation](https://dev.mysql.com/doc/refman/8.4/en/innodb-buffer-pool-resize.html).

Apply the local configuration:

```bash
brew services restart mysql@8.4
```

A successful service-manager message does not mean MySQL is ready to accept
connections. Before provisioning a database or starting Django, confirm a
successful administrator connection with `mysql -u root -p`. After the
application account exists, use its TCP check in the shared guide instead.
If startup briefly refuses a connection, wait a few seconds and retry the
check. If it continues to fail, inspect the service status and error log
rather than resetting data or repeatedly restarting the server.

## 3. Get the project and create a virtual environment

Run this from the parent directory for a new checkout. Use `beta` for normal
development, or the review branch specified by a maintainer:

```bash
git clone --branch beta https://github.com/GrandComicsDatabase/gcd-django.git
cd gcd-django
"$(brew --prefix python@3.13)/bin/python3.13" -m venv .venv
```

Do not clone over an existing checkout or replace its virtual environment.
Continue with [Shared native setup](NATIVE_COMMON.md) to install Python
dependencies, provision the local database and account, and start the sample
site. Keep the terminal with the build-library exports open for that step.

## Service controls

Ctrl-C stops Django at the end of a normal development session. MySQL may
remain running. These commands affect every database hosted by this Homebrew
MySQL instance, not only GCD:

```bash
brew services list
brew services stop mysql@8.4
brew services start mysql@8.4
```

For connection, dependency or startup errors, see
[Troubleshooting](TROUBLESHOOTING.md).
