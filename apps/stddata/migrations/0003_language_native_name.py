# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0002_initial_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='language',
            name='native_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
