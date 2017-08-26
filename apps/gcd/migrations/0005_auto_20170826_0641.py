# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0004_auto_20170826_0641'),
        ('gcd', '0004_initial_creator_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='noncomicworklink',
            name='non_comic_work',
        ),
        migrations.DeleteModel(
            name='NonComicWorkLink',
        ),
        migrations.AddField(
            model_name='award',
            name='no_award_name',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='work_urls',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
