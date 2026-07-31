# Supported Development Versions

The versions below are the provisional development targets while the deployed
beta and production versions are being confirmed. A listed version is treated
as supported only after the compatibility workflow passes.

| Component | Version | Status |
| --- | --- | --- |
| Ubuntu | 24.04 LTS | Selected native Linux and CI baseline |
| Python | 3.14.6 | Compatibility target |
| Django | 5.2 LTS | Supported framework family |
| MySQL | 8.4.10 LTS | Compatibility target |
| Elasticsearch | 9.4.2 | Deferred search-upgrade target |

The core environment deliberately disables Elasticsearch. The application
currently depends on an Elasticsearch 7 client and a custom Elasticsearch 7
Haystack backend, so Elasticsearch 9 support requires a separate application
upgrade and test suite.

## Policy

- Exact Python and service versions are pinned for reproducible validation.
- Patch updates must pass dependency installation, migrations, Django system
  checks, and the published smoke tests before they are accepted.
- Minor and major upgrades require an explicit compatibility review.
- Confirmed beta and production constraints replace these provisional targets
  when they are available.

## Sources

- Python: https://www.python.org/downloads/release/python-3146/
- Django: https://docs.djangoproject.com/en/dev/releases/5.2/
- MySQL: https://dev.mysql.com/downloads/mysql/8.4.html
- MySQL release policy:
  https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html
- Elasticsearch: https://www.elastic.co/downloads/elasticsearch
- Ubuntu: https://ubuntu.com/about/release-cycle
