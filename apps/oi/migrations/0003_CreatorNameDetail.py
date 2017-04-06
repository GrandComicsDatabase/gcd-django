# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0004_CreatorNameDetail'),
        ('oi', '0002_creators'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreatorNameDetailRevision',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('changeset', models.ForeignKey(related_name='creatornamedetailrevisions', to='oi.Changeset')),
                ('creator', models.ForeignKey(related_name='cr_creator_names', to='oi.CreatorRevision')),
                ('creator_name_detail', models.ForeignKey(related_name='cr_creator_name_details', to='gcd.CreatorNameDetail', null=True)),
                ('source', models.ManyToManyField(related_name='cr_namesources', null=True, to='gcd.SourceType', blank=True)),
                ('type', models.ForeignKey(related_name='cr_nametypes', blank=True, to='gcd.NameType', null=True)),
            ],
            options={
                'ordering': ['created', '-id'],
                'db_table': 'oi_creator_name_detail_revision',
                'verbose_name_plural': 'Creator Name Detail Revisions',
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='creatornamedetailsrevision',
            name='changeset',
        ),
        migrations.RemoveField(
            model_name='creatornamedetailsrevision',
            name='creator',
        ),
        migrations.RemoveField(
            model_name='creatornamedetailsrevision',
            name='creator_name_detail',
        ),
        migrations.RemoveField(
            model_name='creatornamedetailsrevision',
            name='source',
        ),
        migrations.RemoveField(
            model_name='creatornamedetailsrevision',
            name='type',
        ),
        migrations.AlterModelOptions(
            name='namerelationrevision',
            options={'ordering': ('gcd_official_name', 'rel_type', 'to_name'), 'verbose_name_plural': 'Name Relation Revisions'},
        ),
        migrations.AlterField(
            model_name='namerelationrevision',
            name='gcd_official_name',
            field=models.ForeignKey(related_name='creator_revise_gcd_official_name', to='oi.CreatorNameDetailRevision'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='namerelationrevision',
            name='to_name',
            field=models.ForeignKey(related_name='creator_revise_to_name', to='oi.CreatorNameDetailRevision'),
            preserve_default=True,
        ),
        migrations.DeleteModel(
            name='CreatorNameDetailsRevision',
        ),
    ]
