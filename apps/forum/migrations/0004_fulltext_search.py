from django.db import migrations

# MySQL FULLTEXT indexes for the forum search (apps/forum/search.py); other
# databases keep the plain substring search.
INDEXES = (
    ("forum_discussion", "forum_discussion_title_ft", "title"),
    ("forum_post", "forum_post_content_ft", "content"),
)


def add_indexes(apps, schema_editor):
    """Add the FULLTEXT indexes on MySQL; other databases keep the plain substring search."""
    if schema_editor.connection.vendor == "mysql":
        for table, name, column in INDEXES:
            schema_editor.execute(f"ALTER TABLE {table} ADD FULLTEXT INDEX {name} ({column})")


def drop_indexes(apps, schema_editor):
    """Drop the FULLTEXT indexes on MySQL, undoing add_indexes."""
    if schema_editor.connection.vendor == "mysql":
        for table, name, column in INDEXES:
            schema_editor.execute(f"ALTER TABLE {table} DROP INDEX {name}")


class Migration(migrations.Migration):
    """FULLTEXT indexes on topic titles and post contents for the search, added outside a transaction."""

    # MySQL cannot run DDL inside a transaction.
    atomic = False

    dependencies = [
        ("forum", "0003_review_and_attachments"),
    ]

    operations = [
        migrations.RunPython(add_indexes, drop_indexes),
    ]
