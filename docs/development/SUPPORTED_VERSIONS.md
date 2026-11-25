# Supported Development Versions

The versions below are the supported development contract. A listed version is
treated as supported only while the compatibility workflow and application test
suite pass.

| Component | Version | Status |
| --- | --- | --- |
| Ubuntu | 24.04 LTS | Selected native Linux and CI baseline |
| Python | `>=3.13,<3.14` | Supported release line |
| Django | 5.2 LTS | Supported framework family |
| MySQL | `>=8.0` | Supported minimum |
| Elasticsearch | `>7.0,<8.0` | Supported dependency range |
| Redis | `7.4` | Optional queued search-update service |

The core environment deliberately disables Elasticsearch. Search-enabled
environments use the existing Elasticsearch 7 client and custom Elasticsearch 7
Haystack backend within the supported range above.

## Native package choices and measured coverage

MySQL `>=8.0` is a compatibility floor, not an instruction to install the newest
available major release. Use the recipe for the selected platform:

| Route | Package selection | Measured sample-data walkthrough |
| --- | --- | --- |
| Docker Compose | `mysql:8.0` | Docker core and optional-search checks |
| Native Ubuntu 24.04 | Ubuntu's `mysql-server` package, MySQL 8.0 | Ubuntu 24.04.5 ARM64, MySQL 8.0.46 |
| Native macOS | Homebrew `mysql@8.4` | Apple Silicon macOS 26.6.2, MySQL 8.4.13 |
| Native WSL2 | Ubuntu 24.04's `mysql-server` package, MySQL 8.0 | Ubuntu 24.04.5 x86_64, MySQL 8.0.46 |

The native walkthroughs used Python 3.13.18. Patch versions here record test
evidence, not permanent dependency pins. The WSL2 run used a pinned source
archive; its result does not establish Docker Desktop/WSL editor integration.
Intel macOS remains unverified. Codespaces is deferred to a separate follow-up.

Do not upgrade or replace an existing MySQL service to match a recipe without
reviewing its data and other users. See [native macOS](NATIVE_MACOS.md),
[native Ubuntu](NATIVE_UBUNTU.md), and [WSL2](WSL2.md) for isolated setup and
platform-specific build dependencies.

## Policy

- Python is restricted to the 3.13 release line.
- MySQL 8.0 is the compatibility floor; newer server versions must continue to
  pass migrations, system checks, and the test suite.
- Elasticsearch must remain within the 7.x dependency range already declared
  in `requirements.txt`.
- Redis 7.4 is limited to the optional local search profile and the existing
  `django-rq`/`haystack-rqueue` integration.
- Patch updates must pass dependency installation, migrations, Django system
  checks, and the published smoke tests before they are accepted.
- Minor and major upgrades require an explicit compatibility review.

## Sources

- Python 3.13: https://docs.python.org/3.13/
- Django: https://docs.djangoproject.com/en/dev/releases/5.2/
- MySQL 8.0: https://dev.mysql.com/doc/refman/8.0/en/
- Elasticsearch 7.17:
  https://www.elastic.co/guide/en/elasticsearch/reference/7.17/index.html
- Redis Open Source version management:
  https://redis.io/docs/latest/operate/oss_and_stack/install/version-mgmt/
- Ubuntu: https://ubuntu.com/about/release-cycle
