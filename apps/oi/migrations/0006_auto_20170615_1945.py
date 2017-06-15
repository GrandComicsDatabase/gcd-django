# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0005_creator_cleanup'),
    ]

    operations = [
        migrations.RenameField(
            model_name='creatorrevision',
            old_name='birth_day',
            new_name='birth_date',
        ),
        migrations.RenameField(
            model_name='creatorrevision',
            old_name='death_day',
            new_name='death_date',
        ),
    ]
