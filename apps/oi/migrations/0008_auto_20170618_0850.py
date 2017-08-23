# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0007_auto_20170618_0717'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatordegreedetailrevision',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetailrevision',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
    ]
