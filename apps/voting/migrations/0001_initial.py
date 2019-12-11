# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Agenda',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('uses_tokens', models.BooleanField(default=False)),
                ('allows_abstentions', models.BooleanField(default=False)),
                ('quorum', models.IntegerField(default=1, help_text='Quorum must always be at least 1', blank=True)),
                ('secret_ballot', models.BooleanField(default=False)),
                ('permission', models.ForeignKey(to='auth.Permission')),
                ('subscribers', models.ManyToManyField(related_name='subscribed_agendas', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AgendaItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('notes', models.TextField(null=True, blank=True)),
                ('state', models.NullBooleanField(choices=[(None, 'Pending'), (True, 'Open'), (False, 'Closed')])),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                ('agenda', models.ForeignKey(related_name='items', to='voting.Agenda')),
                ('owner', models.ForeignKey(related_name='agenda_items', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('subscribers', models.ManyToManyField(related_name='subscribed_items', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'voting_agenda_item',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AgendaMailingList',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('on_agenda_item_add', models.BooleanField(default=False)),
                ('on_agenda_item_open', models.BooleanField(default=False)),
                ('on_vote_open', models.BooleanField(default=False)),
                ('on_vote_close', models.BooleanField(default=False)),
                ('is_primary', models.BooleanField(default=False)),
                ('reminder', models.BooleanField(default=False)),
                ('display_token', models.BooleanField(default=False)),
                ('agenda', models.ForeignKey(related_name='agenda_mailing_lists', to='voting.Agenda')),
                ('group', models.ForeignKey(blank=True, to='auth.Group', null=True)),
            ],
            options={
                'db_table': 'voting_agenda_mailing_list',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ExpectedVoter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('tenure_began', models.DateTimeField()),
                ('tenure_ended', models.DateTimeField(null=True, blank=True)),
                ('agenda', models.ForeignKey(related_name='expected_voters', to='voting.Agenda')),
                ('voter', models.ForeignKey(related_name='voting_expectations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('tenure_began', 'tenure_ended', 'voter__last_name', 'voter__first_name'),
                'db_table': 'voting_expected_voter',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MailingList',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('address', models.EmailField(max_length=75)),
            ],
            options={
                'db_table': 'voting_mailing_list',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Option',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('text', models.TextField(null=True, blank=True)),
                ('ballot_position', models.IntegerField(help_text='Optional whole number used to arrange the options in an order other than alphabetical by name.', null=True, blank=True)),
                ('result', models.NullBooleanField()),
            ],
            options={
                'ordering': ('ballot_position', 'name'),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Receipt',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('vote_key', models.CharField(max_length=64)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Topic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('text', models.TextField(null=True, blank=True)),
                ('open', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('deadline', models.DateTimeField(db_index=True)),
                ('token', models.CharField(max_length=255, null=True, editable=False)),
                ('result_calculated', models.BooleanField(default=False, db_index=True, editable=False)),
                ('invalid', models.BooleanField(default=False, editable=False)),
                ('agenda', models.ForeignKey(related_name='topics', to='voting.Agenda')),
                ('agenda_items', models.ManyToManyField(related_name='topics', to='voting.AgendaItem')),
                ('author', models.ForeignKey(related_name='topics', to=settings.AUTH_USER_MODEL)),
                ('second', models.ForeignKey(related_name='seconded_topics', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('subscribers', models.ManyToManyField(related_name='subscribed_topics', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('created',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rank', models.IntegerField(null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                ('option', models.ForeignKey(related_name='votes', to='voting.Option')),
                ('voter', models.ForeignKey(related_name='votes', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='VoteType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('max_votes', models.IntegerField(default=1, help_text='Having more votes than winners sets up ranked choice voting.  Leave max votes blank to allow as many ranks as options.', null=True, blank=True)),
                ('max_winners', models.IntegerField(default=1, help_text='Having more than one winner allows votes to be cast for up to that many options.')),
            ],
            options={
                'db_table': 'voting_vote_type',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='topic',
            name='vote_type',
            field=models.ForeignKey(related_name='topics', to='voting.VoteType', help_text='Pass / Fail types will automatically create their own Options if none are specified directly.  For other types, add Options below.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='receipt',
            name='topic',
            field=models.ForeignKey(related_name='receipts', to='voting.Topic'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='receipt',
            name='voter',
            field=models.ForeignKey(related_name='receipts', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='option',
            name='topic',
            field=models.ForeignKey(related_name='options', to='voting.Topic', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='option',
            name='voters',
            field=models.ManyToManyField(related_name='voted_options', through='voting.Vote', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='agendamailinglist',
            name='mailing_list',
            field=models.ForeignKey(related_name='agenda_mailing_lists', blank=True, to='voting.MailingList', null=True),
            preserve_default=True,
        ),
    ]
