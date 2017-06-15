# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0003_language_native_name'),
        ('gcd', '0007_DataSource'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='creatornamedetail',
            options={'ordering': ['type__id', 'created', '-id'], 'verbose_name_plural': 'CreatorName Details'},
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='membership_begin_year',
            new_name='membership_year_began',
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='membership_begin_year_uncertain',
            new_name='membership_year_began_uncertain',
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='membership_end_year',
            new_name='membership_year_ended',
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='membership_end_year_uncertain',
            new_name='membership_year_ended_uncertain',
        ),
        migrations.RemoveField(
            model_name='artinfluence',
            name='is_self_identify',
        ),
        migrations.RemoveField(
            model_name='artinfluence',
            name='self_identify_influences_doc',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_date',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_date_uncertain',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_month',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_month_uncertain',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_year',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='birth_year_uncertain',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_date',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_date_uncertain',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_month',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_month_uncertain',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_year',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='death_year_uncertain',
        ),
        migrations.RemoveField(
            model_name='noncomicwork',
            name='work_notes',
        ),
        migrations.AddField(
            model_name='artinfluence',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='artinfluence',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_day',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_day',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='membership',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='membership',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='notes',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='creator',
            name='bio',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creator',
            name='birth_city',
            field=models.CharField(max_length=200, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creator',
            name='birth_province',
            field=models.CharField(max_length=50, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creator',
            name='death_city',
            field=models.CharField(max_length=200, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creator',
            name='death_province',
            field=models.CharField(max_length=50, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creator',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='nametype',
            name='description',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='nametype',
            name='type',
            field=models.CharField(max_length=50, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='noncomicwork',
            name='employer_name',
            field=models.CharField(max_length=200, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='noncomicwork',
            name='work_title',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
