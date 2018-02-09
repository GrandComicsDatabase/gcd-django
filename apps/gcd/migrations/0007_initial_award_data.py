# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.core.management import call_command


def load_initial_award_data(apps, schema_editor):
    call_command('loaddata', 'award')


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0006_award_editable'),
    ]

    operations = [
        migrations.RunPython(load_initial_award_data),
    ]
