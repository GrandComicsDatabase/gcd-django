# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0009_storyrevision_first_line'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='creatorrevision',
            name='data_source',
        ),
    ]
