# Contributing to the GCD web application

This page is the short version. The [README](README.md) and the
[development guides](docs/development/CORE_SETUP.md) hold the details.

## Talk first

The [gcd-tech list](https://groups.google.com/group/gcd-tech/) is the main
place for discussion. If you are new to the code, write there before you
start on a fix. Problems with the code and ideas go in the
[issues](https://github.com/GrandComicsDatabase/gcd-django/issues).

## Set up

Start with the
[development environment chooser](docs/development/CORE_SETUP.md). The
default setup uses Docker Compose:

```bash
git clone --branch beta \
  https://github.com/GrandComicsDatabase/gcd-django.git
cd gcd-django
./bin/dev setup
```

The same page links the native macOS, Ubuntu and WSL2 guides and the
VS Code Dev Container. For failures, see
[troubleshooting](docs/development/TROUBLESHOOTING.md).

## Branches

`beta` is the development branch. Start your branch from `beta` and open
the pull request against `beta`. `master` is, in general, the production
deployment.

## Tests

The tests use pytest. With Docker, run all of them or one folder:

```bash
./bin/dev test
./bin/dev test apps/gcd/tests
```

The native and Dev Container guides give the command for their setup. On
every pull request against `beta`, a GitHub workflow runs a set of these
tests.

## Pull requests

- Fill in the [pull request template](.github/PULL_REQUEST_TEMPLATE.md):
  what the change does and why, and how you checked it.
- If no one seems to be paying attention, ask on the gcd-tech list.

## Wrong data and security

- Wrong data in a record, such as a credit, a date or a name, is not a
  problem of the code. Report it to the
  [Error Tracker](https://errors.comics.org/enter_bug.cgi?product=GCD):
  "Report Information" on an issue page and "let us know" at the foot of a
  page fill in the address of the page.
- Never report a security problem in a public issue. Follow
  [SECURITY.md](SECURITY.md).

## More

The [Technical section on docs.comics.org][technical] and the
[wiki](https://github.com/GrandComicsDatabase/gcd-django/wiki) describe
how the project works.

[technical]: https://docs.comics.org/wiki/Main_Page#Technical_Details
