# -*- coding: utf-8 -*-


from django.db import migrations
from django.core.management import call_command


def load_initial_data(apps, schema_editor):
    # Only load if not already present- this is to support running the
    # migrations with --fake-initial to upgrade from South.
    for model in ('ConditionGradeScale', 'ConditionGrade'):
        if not apps.get_model('mycomics', model).objects.exists():
            call_command('loaddata', model.lower())


class Migration(migrations.Migration):

    dependencies = [
        ('mycomics', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_initial_data),
    ]
