"""
Wait for the transactions that wait for a row lock, as the database server
shows them: MySQL in its Performance Schema, MariaDB, which has no such
tables, in its Information Schema.
"""
import time

from django.db import connection

MYSQL_LOCK_WAITS = (
  'SELECT COUNT(*) FROM performance_schema.data_lock_waits w '
  'JOIN performance_schema.data_locks l '
  'ON l.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID '
  'WHERE l.OBJECT_SCHEMA = DATABASE() AND l.OBJECT_NAME = %s')

MARIADB_LOCK_WAITS = (
  'SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w '
  'JOIN information_schema.INNODB_LOCKS l '
  'ON l.lock_id = w.requested_lock_id '
  "WHERE l.lock_table = CONCAT('`', DATABASE(), '`.`', %s, '`')")


def lock_waits(cursor, table):
    """Return how many transactions wait for a lock on a row of table."""
    if cursor.db.mysql_is_mariadb:
        cursor.execute(MARIADB_LOCK_WAITS, [table])
    else:
        cursor.execute(MYSQL_LOCK_WAITS, [table])
    return cursor.fetchone()[0]


def wait_for_lock_waits(table, count=1, timeout=30):
    """
    Wait until count transactions wait for a lock on a row of table, as
    the server shows it.
    """
    # InnoDB refreshes the Information Schema lock tables that MariaDB
    # reads only when they were not read in the last 0.1 seconds.
    interval = 0.2 if connection.mysql_is_mariadb else 0.05
    end = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < end:
            if lock_waits(cursor, table) >= count:
                return
            time.sleep(interval)
    raise AssertionError('fewer than %d transactions wait for %s'
                         % (count, table))
