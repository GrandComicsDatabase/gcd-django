# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0005_delete_creatornamedetails'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreatorDataSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField()),
                ('field', models.CharField(max_length=256)),
                ('source_type', models.ForeignKey(to='gcd.SourceType')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Creator Data Source',
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='creator',
            name='bio_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_city_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_country_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_date_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_month_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_province_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_year_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_city_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_country_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_date_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_month_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_province_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_year_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='portrait_source',
        ),
        migrations.AddField(
            model_name='creator',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
    ]
