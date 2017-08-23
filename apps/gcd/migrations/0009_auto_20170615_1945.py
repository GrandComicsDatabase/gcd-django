# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0008_creator_cleanup'),
    ]

    operations = [
        migrations.RenameField(
            model_name='creator',
            old_name='birth_day',
            new_name='birth_date',
        ),
        migrations.RenameField(
            model_name='creator',
            old_name='death_day',
            new_name='death_date',
        ),
    ]
