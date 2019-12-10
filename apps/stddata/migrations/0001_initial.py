# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(unique=True, max_length=10)),
                ('name', models.CharField(max_length=255, db_index=True)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'Countries',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(unique=True, max_length=3)),
                ('name', models.CharField(max_length=100, db_index=True)),
                ('is_decimal', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'Currencies',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Date',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('year', models.CharField(db_index=True, max_length=4, blank=True)),
                ('month', models.CharField(db_index=True, max_length=2, blank=True)),
                ('day', models.CharField(db_index=True, max_length=2, blank=True)),
                ('year_uncertain', models.BooleanField(default=False)),
                ('month_uncertain', models.BooleanField(default=False)),
                ('day_uncertain', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('year', 'month', 'day'),
                'verbose_name_plural': 'Dates',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(unique=True, max_length=10)),
                ('name', models.CharField(max_length=255, db_index=True)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
    ]
