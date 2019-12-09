# -*- coding: utf-8 -*-


from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0005_issue_volume_not_printed'),
    ]

    operations = [
        migrations.AddField(
            model_name='award',
            name='created',
            field=models.DateTimeField(default=datetime.datetime(2018, 1, 1, 0, 0), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='award',
            name='deleted',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='modified',
            field=models.DateTimeField(default=datetime.datetime(2018, 1, 1, 0, 0), auto_now=True, db_index=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='award',
            name='notes',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
