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

The core environment deliberately disables Elasticsearch. Search-enabled
environments use the existing Elasticsearch 7 client and custom Elasticsearch 7
Haystack backend within the supported range above.

## Policy

- Python is restricted to the 3.13 release line.
- MySQL 8.0 is the compatibility floor; newer server versions must continue to
  pass migrations, system checks, and the test suite.
- Elasticsearch must remain within the 7.x dependency range already declared
  in `requirements.txt`.
- Patch updates must pass dependency installation, migrations, Django system
  checks, and the published smoke tests before they are accepted.
- Minor and major upgrades require an explicit compatibility review.

## Sources

- Python 3.13: https://docs.python.org/3.13/
- Django: https://docs.djangoproject.com/en/dev/releases/5.2/
- MySQL 8.0: https://dev.mysql.com/doc/refman/8.0/en/
- Elasticsearch 7.17:
  https://www.elastic.co/guide/en/elasticsearch/reference/7.17/index.html
- Ubuntu: https://ubuntu.com/about/release-cycle
