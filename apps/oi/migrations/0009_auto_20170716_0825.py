# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0012_auto_20170716_0825'),
        ('oi', '0008_auto_20170618_0850'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatorawardrevision',
            name='award',
            field=models.ForeignKey(to='gcd.AwardType', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorartinfluencerevision',
            name='influence_name',
            field=models.CharField(max_length=200, blank=True),
            preserve_default=True,
        ),
    ]
