# SPDX-FileCopyrightText: Grand Comics Database contributors
# SPDX-License-Identifier: GPL-3.0-only

"""Regression tests for change-history comments."""

from importlib import import_module

from django.db import migrations

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
