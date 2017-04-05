# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0003_creators'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreatorNameDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creator_names', to='gcd.Creator')),
                ('source', models.ManyToManyField(related_name='namesources', null=True, to='gcd.SourceType', blank=True)),
                ('type', models.ForeignKey(related_name='nametypes', blank=True, to='gcd.NameType', null=True)),
            ],
            options={
                'ordering': ('type',),
                'verbose_name_plural': 'CreatorName Details',
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='creatornamedetails',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='creatornamedetails',
            name='source',
        ),
        migrations.RemoveField(
            model_name='creatornamedetails',
            name='type',
        ),
        migrations.AlterField(
            model_name='namerelation',
            name='gcd_official_name',
            field=models.ForeignKey(related_name='creator_gcd_official_name', to='gcd.CreatorNameDetail'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='namerelation',
            name='to_name',
            field=models.ForeignKey(related_name='to_name', to='gcd.CreatorNameDetail'),
            preserve_default=True,
        ),
    ]
