# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0004_auto_20170826_0641'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='noncomicworkyearrevision',
            name='changeset',
        ),
        migrations.RemoveField(
            model_name='noncomicworkyearrevision',
            name='creator_noncomicworkyear',
        ),
        migrations.RemoveField(
            model_name='noncomicworkyearrevision',
            name='non_comic_work',
        ),
        migrations.DeleteModel(
            name='NonComicWorkYearRevision',
        ),
        migrations.AlterField(
            model_name='creatorawardrevision',
            name='award_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
