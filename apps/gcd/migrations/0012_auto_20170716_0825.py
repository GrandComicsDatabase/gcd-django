# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0011_auto_20170618_0921'),
    ]

    operations = [
        migrations.CreateModel(
            name='AwardType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'AwardTypes',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='award',
            name='award',
            field=models.ForeignKey(to='gcd.AwardType', null=True),
            preserve_default=True,
        ),
    ]
