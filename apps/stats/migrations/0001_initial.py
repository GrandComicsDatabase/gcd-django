# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0002_initial_data'),
        ('gcd', '0002_initial_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CountStats',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=40, db_index=True)),
                ('count', models.IntegerField()),
                ('country', models.ForeignKey(to='stddata.Country', null=True)),
                ('language', models.ForeignKey(to='stddata.Language', null=True)),
            ],
            options={
                'db_table': 'stats_count_stats',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Download',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RecentIndexedIssue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('issue', models.ForeignKey(to='gcd.Issue')),
                ('language', models.ForeignKey(to='stddata.Language', null=True)),
            ],
            options={
                'db_table': 'stats_recent_indexed_issue',
            },
            bases=(models.Model,),
        ),
    ]
