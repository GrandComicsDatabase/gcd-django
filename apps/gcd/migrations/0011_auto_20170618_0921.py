# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0010_auto_20170618_0846'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatordegreedetail',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
    ]
