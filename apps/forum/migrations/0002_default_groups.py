from django.db import migrations

# One group per GCD email list, as described in the Email Lists FAQ.
# gcd-contact stays an email address: it is meant for people without an account.
MAIN = (
    ("gcd-main", "Indexing questions, missing credits, creator identification and "
                 "official GCD business. Controversial questions move to gcd-policy."),
    ("gcd-tech", "Technical side of the project: database design, data files, "
                 "software and feature beta testing."),
    ("gcd-policy", "Debating day-to-day operations: formatting, new or changed fields, "
                   "whether an item belongs in the database, approval problems."),
    ("gcd-chat", "General comics talk: history, industry, collecting, characters, "
                 "stories, creators. Mark off-topic threads with OT."),
    ("gcd-mycomics-users", "The experience of using my.comics.org: what works, "
                           "what doesn't, and what to improve next."),
)
INTERNATIONAL = (
    ("gcd-canada", ""),
    ("gcd-deutschland", "de"),
    ("gcd-france", "fr"),
    ("gcd-italia", "it"),
    ("gcd-nederland-vlaanderen", "nl"),
    ("gcd-norge", "no"),
    ("gcd-sverige", "sv"),
    ("gcd-uk", "en"),
)
SPECIALIZED = (
    # name, description, read access, post access
    ("gcd-editor", "Editors discuss indexing and correcting data. By invitation only.",
     "members", "members"),
    ("gcd-board", "Board policy and votes. Anyone can read; Board members post.",
     "public", "members"),
    ("gcd-error", "Report an error in the database. Editors read every report; "
                  "you see the reports you opened.", "members", "users"),
)


def seed_groups(apps, schema_editor):
    Category = apps.get_model("forum", "Category")
    db = schema_editor.connection.alias
    position = 0
    for name, description in MAIN:
        Category.objects.using(db).get_or_create(slug=name, defaults={
            "name": name, "description": description, "section": "main",
            "read_access": "public", "position": position})
        position += 1
    for name, language in INTERNATIONAL:
        Category.objects.using(db).get_or_create(slug=name, defaults={
            "name": name, "section": "international", "language": language,
            "read_access": "public",
            "description": "Indexing help and comics of the country, "
                           "in the language of the country.",
            "position": position})
        position += 1
    for name, description, read_access, post_access in SPECIALIZED:
        Category.objects.using(db).get_or_create(slug=name, defaults={
            "name": name, "description": description, "section": "specialized",
            "read_access": read_access, "post_access": post_access,
            "position": position})
        position += 1


class Migration(migrations.Migration):
    dependencies = [("forum", "0001_initial")]
    # Never remove groups or user discussions when rolling back the data step.
    operations = [migrations.RunPython(seed_groups, migrations.RunPython.noop)]
