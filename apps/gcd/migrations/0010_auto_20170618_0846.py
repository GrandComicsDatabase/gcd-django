# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0009_auto_20170615_1945'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatordegreedetail',
            name='notes',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='notes',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
