# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0002_creators'),
    ]

    operations = [
        migrations.AddField(
            model_name='creatornoncomicworkrevision',
            name='work_links',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornoncomicworkrevision',
            name='work_years',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatornoncomicworkrevision',
            name='employer_name',
            field=models.CharField(default='', max_length=200, blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='creatornoncomicworkrevision',
            name='work_title',
            field=models.CharField(default='', max_length=255, blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='creatorrevision',
            name='birth_city',
            field=models.CharField(default='', max_length=200, blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='creatorrevision',
            name='birth_province',
            field=models.CharField(default='', max_length=50, blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='creatorrevision',
            name='death_city',
            field=models.CharField(default='', max_length=200, blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='creatorrevision',
            name='death_province',
            field=models.CharField(default='', max_length=50, blank=True),
            preserve_default=False,
        ),
    ]
