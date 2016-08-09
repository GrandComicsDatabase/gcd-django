# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.core.management import call_command


def load_initial_data(apps, schema_editor):
    # Only load if not already present- this is to support running the
    # migrations with --fake-initial to upgrade from South.
    for model in ('Country', 'Currency', 'Language'):
        if not apps.get_model('stddata', model).objects.exists():
            call_command('loaddata', model.lower())


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_initial_data),
    ]
