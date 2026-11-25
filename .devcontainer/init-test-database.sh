#!/usr/bin/env bash
# MySQL-image first-init hook. Runs inside db, never in the editor container.
set -euo pipefail

database="${MYSQL_DATABASE:-}"
application_user="${MYSQL_USER:-}"
if [[ ! "$database" =~ ^gcd_dev(_[a-z0-9_]+)?$ &&
      "$database" != "gcd_django_dev" ]] || (( ${#database} > 59 )); then
  echo "Dev Container grants require a development database named gcd_dev, gcd_django_dev, or gcd_dev_* (at most 59 characters)." >&2
  exit 2
fi
if [[ ! "$application_user" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ ||
      "$application_user" == "root" ]] || (( ${#application_user} > 32 )); then
  echo "Dev Container grants require a non-root application user with a simple name (at most 32 characters)." >&2
  exit 2
fi
if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
  echo "MYSQL_ROOT_PASSWORD is required by the database-only init hook." >&2
  exit 2
fi

# The image's temporary first-init server accepts local socket connections.
# Supply its credential through the process environment, not argv or SQL.
export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
mysql_admin=(mysql --protocol=socket --user=root --batch --skip-column-names)
partial_revokes="$("${mysql_admin[@]}" --execute='SELECT @@GLOBAL.partial_revokes')"
if [[ "$partial_revokes" != "0" ]]; then
  echo "Dev Container grants require partial_revokes=OFF; no grants changed." >&2
  exit 2
fi

# Database GRANT identifiers are patterns when partial_revokes is disabled.
# Clear grants from the fresh image-created account without assuming how that
# image escaped its initial schema grant. Then grant only the exact application
# and test schemas, never global privileges or GRANT OPTION.
escaped_database="${database//_/\\_}"
"${mysql_admin[@]}" <<SQL
REVOKE ALL PRIVILEGES, GRANT OPTION FROM '$application_user'@'%';
GRANT ALL PRIVILEGES ON \`$escaped_database\`.* TO '$application_user'@'%';
GRANT ALL PRIVILEGES ON \`test\\_$escaped_database\`.* TO '$application_user'@'%';
SQL
