# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import apps.oi.models


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0003_auto_20170825_2035'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='noncomicworklinkrevision',
            name='changeset',
        ),
        migrations.RemoveField(
            model_name='noncomicworklinkrevision',
            name='creator_noncomicworklink',
        ),
        migrations.RemoveField(
            model_name='noncomicworklinkrevision',
            name='non_comic_work',
        ),
        migrations.DeleteModel(
            name='NonComicWorkLinkRevision',
        ),
        migrations.RemoveField(
            model_name='creatornoncomicworkrevision',
            name='work_links',
        ),
        migrations.AddField(
            model_name='creatorawardrevision',
            name='no_award_name',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornoncomicworkrevision',
            name='work_urls',
            field=models.TextField(blank=True, validators=[apps.oi.models.MultiURLValidator()]),
            preserve_default=True,
        ),
    ]
