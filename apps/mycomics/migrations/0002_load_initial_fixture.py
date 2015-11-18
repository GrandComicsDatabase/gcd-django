# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.core.management import call_command


def load_initial_data(apps, schema_editor):
    call_command("loaddata", "initial_data.json")


class Migration(migrations.Migration):

    dependencies = [
        ('mycomics', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_initial_data),
    ]
