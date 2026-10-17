from django.db import migrations

# The forum is read by GCD users only: the groups that 0002 opened to visitors
# become readable by any GCD user. The admin can still open a single group.

BOARD = ("Board policy and votes. Anyone can read; Board members post.",
         "Board policy and votes. Any GCD user can read; Board members post.")


def close_groups(apps, schema_editor):
    """Make every public group readable by GCD users only, and say so in gcd-board's default description."""
    Category = apps.get_model("forum", "Category")
    groups = Category.objects.using(schema_editor.connection.alias)
    groups.filter(read_access="public").update(read_access="users")
    groups.filter(slug="gcd-board", description=BOARD[0]).update(description=BOARD[1])


class Migration(migrations.Migration):
    """Make the forum readable by GCD users only. Rolling back changes nothing: opening a group to visitors
    stays the admin's decision, and groups already open stay open."""

    dependencies = [
        ("forum", "0004_fulltext_search"),
    ]

    operations = [
        migrations.RunPython(close_groups, migrations.RunPython.noop),
    ]
