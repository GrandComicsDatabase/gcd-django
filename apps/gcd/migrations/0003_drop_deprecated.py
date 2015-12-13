# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0002_initial_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='brand',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='imprint_count',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='is_master',
        ),
        migrations.RemoveField(
            model_name='publisher',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='series',
            name='publication_notes',
        ),
        migrations.AlterField(
            model_name='series',
            name='issue_count',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
    ]
