# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0002_initial_data'),
        ('indexer', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndexCredit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('run', models.CharField(max_length=255, null=True)),
                ('notes', models.TextField(null=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('indexer', models.ForeignKey(related_name='index_credit_set', to='indexer.Indexer')),
                ('series', models.ForeignKey(related_name='index_credit_set', to='gcd.Series')),
            ],
            options={
                'db_table': 'legacy_series_indexers',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MigrationStoryStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('reprint_needs_inspection', models.BooleanField(default=False, db_index=True)),
                ('reprint_confirmed', models.BooleanField(default=False, db_index=True)),
                ('reprint_original_notes', models.TextField(null=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('story', models.OneToOneField(related_name='migration_status', to='gcd.Story')),
            ],
            options={
                'db_table': 'legacy_migration_story_status',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Reservation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.IntegerField(db_index=True)),
                ('expires', models.DateField(null=True, blank=True)),
                ('created', models.DateTimeField(auto_now=True)),
                ('indexer', models.ForeignKey(related_name='reservation_set', to='indexer.Indexer')),
                ('issue', models.ForeignKey(related_name='reservation_set', to='gcd.Issue')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
