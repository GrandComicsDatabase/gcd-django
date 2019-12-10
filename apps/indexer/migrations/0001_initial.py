# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0002_initial_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Error',
            fields=[
                ('error_key', models.CharField(max_length=40, serialize=False, editable=False, primary_key=True)),
                ('error_text', models.TextField(null=True, blank=True)),
                ('is_safe', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImpGrant',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('imps', models.IntegerField()),
                ('grant_type', models.CharField(max_length=50)),
                ('notes', models.TextField()),
            ],
            options={
                'db_table': 'indexer_imp_grant',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Indexer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('interests', models.TextField(null=True, blank=True)),
                ('opt_in_email', models.BooleanField(default=False, db_index=True)),
                ('from_where', models.TextField(blank=True)),
                ('max_reservations', models.IntegerField(default=1)),
                ('max_ongoing', models.IntegerField(default=0)),
                ('is_new', models.BooleanField(default=False, db_index=True)),
                ('is_banned', models.BooleanField(default=False, db_index=True)),
                ('deceased', models.BooleanField(default=False, db_index=True)),
                ('registration_key', models.CharField(max_length=40, null=True, editable=False, db_index=True)),
                ('registration_expires', models.DateField(db_index=True, null=True, blank=True)),
                ('imps', models.IntegerField(default=0)),
                ('issue_detail', models.IntegerField(default=1)),
                ('notify_on_approve', models.BooleanField(default=True, db_index=True)),
                ('collapse_compare_view', models.BooleanField(default=False, db_index=True)),
                ('show_wiki_links', models.BooleanField(default=True, db_index=True)),
                ('country', models.ForeignKey(related_name='indexers', to='stddata.Country')),
                ('languages', models.ManyToManyField(related_name='indexers', db_table='gcd_indexer_languages', to='stddata.Language')),
                ('mentor', models.ForeignKey(related_name='mentees', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user__last_name', 'user__first_name'],
                'permissions': (('can_upload_cover', 'Can upload covers'), ('can_reserve', 'Can reserve a record for add, edit or delete'), ('can_approve', 'Can approve a change to a record'), ('can_cancel', 'Can cancel a pending change they did not open'), ('can_mentor', 'Can mentor new indexers'), ('can_vote', 'Can vote in GCD elections'), ('can_publish', 'Can publish non-database content on the web site'), ('on_board', 'Is on the Board of Directors')),
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='impgrant',
            name='indexer',
            field=models.ForeignKey(related_name='imp_grant_set', to='indexer.Indexer'),
            preserve_default=True,
        ),
    ]
