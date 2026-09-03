# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Regression tests for change-history comments."""

from importlib import import_module

from django.db import connection, migrations

from apps.oi.forms.support import _get_comments_form_field
from apps.oi.models import ChangesetComment


def test_changeset_comment_text_uses_utf8mb4_collation():
    """Comments declare a collation that supports four-byte Unicode."""
    text_field = ChangesetComment._meta.get_field('text')

    assert text_field.db_collation == 'utf8mb4_unicode_ci'


def test_changeset_comment_round_trips_four_byte_unicode(
    db,
    any_changeset,
    any_indexer,
):
    """A change-history comment can retain emoji text."""
    comment = ChangesetComment.objects.create(
        changeset=any_changeset,
        commenter=any_indexer,
        text='Looks good 👍',
        old_state=any_changeset.state,
        new_state=any_changeset.state,
    )

    assert ChangesetComment.objects.get(pk=comment.pk).text == 'Looks good 👍'


def test_comments_form_no_longer_claims_emojis_are_unsupported():
    """The user-facing comments help text reflects the database capability."""
    comment_field = _get_comments_form_field()

    assert 'emoji' not in comment_field.help_text.lower()


def test_comment_charset_migration_requires_online_ddl():
    """The production migration must fail instead of blocking writes."""
    migration_module = import_module(
        'apps.oi.migrations.0067_changeset_comment_utf8mb4',
    )
    operation = migration_module.Migration.operations[0]

    assert isinstance(operation, migrations.RunSQL)
    assert 'CHARACTER SET utf8mb4' in operation.sql
    assert 'COLLATE utf8mb4_unicode_ci' in operation.sql
    assert 'ALGORITHM=INPLACE' in operation.sql
    assert 'LOCK=NONE' in operation.sql


def test_comment_charset_migration_runs_online_on_legacy_mysql_column(db):
    """The online DDL works when converting a legacy utf8mb3 column."""
    migration_module = import_module(
        'apps.oi.migrations.0067_changeset_comment_utf8mb4',
    )
    operation = migration_module.Migration.operations[0]
    table_name = 'issue_629_comment_ddl_probe'
    sql = operation.sql.replace(
        '`oi_changeset_comment`',
        f'`{table_name}`',
    )

    with connection.cursor() as cursor:
        cursor.execute(f'DROP TABLE IF EXISTS `{table_name}`')
        try:
            cursor.execute(
                f'CREATE TABLE `{table_name}` ('
                'text longtext CHARACTER SET utf8mb3 '
                'COLLATE utf8mb3_unicode_ci NOT NULL'
                ') ENGINE=InnoDB',
            )
            cursor.execute(sql)
            cursor.execute(
                'SELECT CHARACTER_SET_NAME, COLLATION_NAME '
                'FROM information_schema.COLUMNS '
                'WHERE TABLE_SCHEMA = DATABASE() '
                'AND TABLE_NAME = %s AND COLUMN_NAME = %s',
                [table_name, 'text'],
            )

            assert cursor.fetchone() == ('utf8mb4', 'utf8mb4_unicode_ci')
        finally:
            cursor.execute(f'DROP TABLE IF EXISTS `{table_name}`')
