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
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('source_type', models.ForeignKey(to='gcd.SourceType')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Creator Data Source',
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='biosource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='biosource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='birthcitysource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='birthcitysource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='birthcountrysource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='birthcountrysource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='birthdatesource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='birthdatesource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='birthmonthsource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='birthmonthsource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='birthprovincesource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='birthprovincesource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='birthyearsource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='birthyearsource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='deathcitysource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='deathcitysource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='deathcountrysource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='deathcountrysource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='deathdatesource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='deathdatesource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='deathmonthsource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='deathmonthsource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='deathprovincesource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='deathprovincesource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='deathyearsource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='deathyearsource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='portraitsource',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='portraitsource',
            name='source_type',
        ),
        migrations.RemoveField(
            model_name='artinfluence',
            name='influence_source',
        ),
        migrations.RemoveField(
            model_name='award',
            name='award_source',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='bio_source',
        ),
    ]
