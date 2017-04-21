# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0006_DataSource'),
        ('oi', '0004_DataSource'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BioSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_city_source',
        ),
        migrations.DeleteModel(
            name='BirthCitySource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_country_source',
        ),
        migrations.DeleteModel(
            name='BirthCountrySource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_date_source',
        ),
        migrations.DeleteModel(
            name='BirthDateSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_month_source',
        ),
        migrations.DeleteModel(
            name='BirthMonthSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_province_source',
        ),
        migrations.DeleteModel(
            name='BirthProvinceSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_year_source',
        ),
        migrations.DeleteModel(
            name='BirthYearSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_city_source',
        ),
        migrations.DeleteModel(
            name='DeathCitySource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_country_source',
        ),
        migrations.DeleteModel(
            name='DeathCountrySource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_date_source',
        ),
        migrations.DeleteModel(
            name='DeathDateSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_month_source',
        ),
        migrations.DeleteModel(
            name='DeathMonthSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_province_source',
        ),
        migrations.DeleteModel(
            name='DeathProvinceSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_year_source',
        ),
        migrations.DeleteModel(
            name='DeathYearSource',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='portrait_source',
        ),
        migrations.DeleteModel(
            name='PortraitSource',
        ),
        migrations.RemoveField(
            model_name='creatornamedetail',
            name='description',
        ),
        migrations.RemoveField(
            model_name='creatornamedetail',
            name='source',
        ),
        migrations.RemoveField(
            model_name='creatorschooldetail',
            name='school_source',
        ),
        migrations.RemoveField(
            model_name='membership',
            name='membership_source',
        ),
        migrations.RemoveField(
            model_name='namerelation',
            name='rel_source',
        ),
        migrations.RemoveField(
            model_name='noncomicwork',
            name='work_source',
        ),
        migrations.AddField(
            model_name='creator',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordegreedetail',
            name='created',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatordegreedetail',
            name='deleted',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordegreedetail',
            name='modified',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatordegreedetail',
            name='reserved',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetail',
            name='created',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatornamedetail',
            name='deleted',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetail',
            name='modified',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatornamedetail',
            name='reserved',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='created',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='deleted',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='modified',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='reserved',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='namerelation',
            name='created',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='namerelation',
            name='deleted',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='namerelation',
            name='modified',
            field=models.DateTimeField(default=datetime.date(2017, 4, 21), auto_now=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='namerelation',
            name='reserved',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
    ]
