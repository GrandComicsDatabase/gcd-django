# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0006_award_editable'),
        ('oi', '0005_issuerevision_volume_not_printed'),
    ]

    operations = [
        migrations.CreateModel(
            name='AwardRevision',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('name', models.CharField(max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('award', models.ForeignKey(related_name='revisions', to='gcd.Award', null=True)),
                ('changeset', models.ForeignKey(related_name='awardrevisions', to='oi.Changeset')),
            ],
            options={
                'ordering': ['created', '-id'],
                'db_table': 'oi_award_revision',
                'verbose_name_plural': 'Award Revisions',
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='creatorrelationrevision',
            options={'ordering': ('to_creator', 'relation_type', 'from_creator'), 'verbose_name_plural': 'Creator Relation Revisions'},
        ),
    ]
