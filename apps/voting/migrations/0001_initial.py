# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'MailingList'
        db.create_table('voting_mailing_list', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('address', self.gf('django.db.models.fields.EmailField')(max_length=75)),
        ))
        db.send_create_signal('voting', ['MailingList'])

        # Adding model 'Agenda'
        db.create_table('voting_agenda', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('permission', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.Permission'])),
            ('uses_tokens', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('allows_abstentions', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('quorum', self.gf('django.db.models.fields.IntegerField')(default=1, blank=True)),
            ('secret_ballot', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('voting', ['Agenda'])

        # Adding M2M table for field subscribers on 'Agenda'
        db.create_table('voting_agenda_subscribers', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('agenda', models.ForeignKey(orm['voting.agenda'], null=False)),
            ('user', models.ForeignKey(orm['auth.user'], null=False))
        ))
        db.create_unique('voting_agenda_subscribers', ['agenda_id', 'user_id'])

        # Adding model 'AgendaItem'
        db.create_table('voting_agenda_item', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('agenda', self.gf('django.db.models.fields.related.ForeignKey')(related_name='items', to=orm['voting.Agenda'])),
            ('notes', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='agenda_items', null=True, to=orm['auth.User'])),
            ('state', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, null=True, blank=True)),
        ))
        db.send_create_signal('voting', ['AgendaItem'])

        # Adding M2M table for field subscribers on 'AgendaItem'
        db.create_table('voting_agenda_item_subscribers', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('agendaitem', models.ForeignKey(orm['voting.agendaitem'], null=False)),
            ('user', models.ForeignKey(orm['auth.user'], null=False))
        ))
        db.create_unique('voting_agenda_item_subscribers', ['agendaitem_id', 'user_id'])

        # Adding model 'AgendaMailingList'
        db.create_table('voting_agenda_mailing_list', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('agenda', self.gf('django.db.models.fields.related.ForeignKey')(related_name='agenda_mailing_lists', to=orm['voting.Agenda'])),
            ('mailing_list', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='agenda_mailing_lists', null=True, to=orm['voting.MailingList'])),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.Group'], null=True, blank=True)),
            ('on_agenda_item_add', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('on_agenda_item_open', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('on_vote_open', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('on_vote_close', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_primary', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('reminder', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('display_token', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('voting', ['AgendaMailingList'])

        # Adding model 'VoteType'
        db.create_table('voting_vote_type', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('max_votes', self.gf('django.db.models.fields.IntegerField')(default=1, null=True, blank=True)),
            ('max_winners', self.gf('django.db.models.fields.IntegerField')(default=1)),
        ))
        db.send_create_signal('voting', ['VoteType'])

        # Adding model 'Topic'
        db.create_table('voting_topic', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('text', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('agenda', self.gf('django.db.models.fields.related.ForeignKey')(related_name='topics', to=orm['voting.Agenda'])),
            ('vote_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='topics', to=orm['voting.VoteType'])),
            ('author', self.gf('django.db.models.fields.related.ForeignKey')(related_name='topics', to=orm['auth.User'])),
            ('second', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='seconded_topics', null=True, to=orm['auth.User'])),
            ('open', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('deadline', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('token', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('result_calculated', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('invalid', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('voting', ['Topic'])

        # Adding M2M table for field agenda_items on 'Topic'
        db.create_table('voting_topic_agenda_items', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('topic', models.ForeignKey(orm['voting.topic'], null=False)),
            ('agendaitem', models.ForeignKey(orm['voting.agendaitem'], null=False))
        ))
        db.create_unique('voting_topic_agenda_items', ['topic_id', 'agendaitem_id'])

        # Adding M2M table for field subscribers on 'Topic'
        db.create_table('voting_topic_subscribers', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('topic', models.ForeignKey(orm['voting.topic'], null=False)),
            ('user', models.ForeignKey(orm['auth.user'], null=False))
        ))
        db.create_unique('voting_topic_subscribers', ['topic_id', 'user_id'])

        # Adding model 'Option'
        db.create_table('voting_option', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('text', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('ballot_position', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('topic', self.gf('django.db.models.fields.related.ForeignKey')(related_name='options', null=True, to=orm['voting.Topic'])),
            ('result', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
        ))
        db.send_create_signal('voting', ['Option'])

        # Adding model 'Receipt'
        db.create_table('voting_receipt', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('topic', self.gf('django.db.models.fields.related.ForeignKey')(related_name='receipts', to=orm['voting.Topic'])),
            ('voter', self.gf('django.db.models.fields.related.ForeignKey')(related_name='receipts', to=orm['auth.User'])),
            ('vote_key', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('voting', ['Receipt'])

        # Adding model 'Vote'
        db.create_table('voting_vote', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('voter', self.gf('django.db.models.fields.related.ForeignKey')(related_name='votes', null=True, to=orm['auth.User'])),
            ('option', self.gf('django.db.models.fields.related.ForeignKey')(related_name='votes', to=orm['voting.Option'])),
            ('rank', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, null=True, blank=True)),
        ))
        db.send_create_signal('voting', ['Vote'])

        # Adding model 'ExpectedVoter'
        db.create_table('voting_expected_voter', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('voter', self.gf('django.db.models.fields.related.ForeignKey')(related_name='voting_expectations', to=orm['auth.User'])),
            ('agenda', self.gf('django.db.models.fields.related.ForeignKey')(related_name='expected_voters', to=orm['voting.Agenda'])),
            ('tenure_began', self.gf('django.db.models.fields.DateTimeField')()),
            ('tenure_ended', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('voting', ['ExpectedVoter'])


    def backwards(self, orm):
        # Deleting model 'MailingList'
        db.delete_table('voting_mailing_list')

        # Deleting model 'Agenda'
        db.delete_table('voting_agenda')

        # Removing M2M table for field subscribers on 'Agenda'
        db.delete_table('voting_agenda_subscribers')

        # Deleting model 'AgendaItem'
        db.delete_table('voting_agenda_item')

        # Removing M2M table for field subscribers on 'AgendaItem'
        db.delete_table('voting_agenda_item_subscribers')

        # Deleting model 'AgendaMailingList'
        db.delete_table('voting_agenda_mailing_list')

        # Deleting model 'VoteType'
        db.delete_table('voting_vote_type')

        # Deleting model 'Topic'
        db.delete_table('voting_topic')

        # Removing M2M table for field agenda_items on 'Topic'
        db.delete_table('voting_topic_agenda_items')

        # Removing M2M table for field subscribers on 'Topic'
        db.delete_table('voting_topic_subscribers')

        # Deleting model 'Option'
        db.delete_table('voting_option')

        # Deleting model 'Receipt'
        db.delete_table('voting_receipt')

        # Deleting model 'Vote'
        db.delete_table('voting_vote')

        # Deleting model 'ExpectedVoter'
        db.delete_table('voting_expected_voter')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'voting.agenda': {
            'Meta': {'object_name': 'Agenda'},
            'allows_abstentions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'permission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Permission']"}),
            'quorum': ('django.db.models.fields.IntegerField', [], {'default': '1', 'blank': 'True'}),
            'secret_ballot': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'subscribers': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'subscribed_agendas'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'uses_tokens': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'voting.agendaitem': {
            'Meta': {'object_name': 'AgendaItem', 'db_table': "'voting_agenda_item'"},
            'agenda': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'items'", 'to': "orm['voting.Agenda']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'notes': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'agenda_items'", 'null': 'True', 'to': "orm['auth.User']"}),
            'state': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'subscribers': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'subscribed_items'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'null': 'True', 'blank': 'True'})
        },
        'voting.agendamailinglist': {
            'Meta': {'object_name': 'AgendaMailingList', 'db_table': "'voting_agenda_mailing_list'"},
            'agenda': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'agenda_mailing_lists'", 'to': "orm['voting.Agenda']"}),
            'display_token': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_primary': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'mailing_list': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'agenda_mailing_lists'", 'null': 'True', 'to': "orm['voting.MailingList']"}),
            'on_agenda_item_add': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'on_agenda_item_open': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'on_vote_close': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'on_vote_open': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'reminder': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'voting.expectedvoter': {
            'Meta': {'ordering': "('tenure_began', 'tenure_ended', 'voter__last_name', 'voter__first_name')", 'object_name': 'ExpectedVoter', 'db_table': "'voting_expected_voter'"},
            'agenda': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'expected_voters'", 'to': "orm['voting.Agenda']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tenure_began': ('django.db.models.fields.DateTimeField', [], {}),
            'tenure_ended': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'voter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'voting_expectations'", 'to': "orm['auth.User']"})
        },
        'voting.mailinglist': {
            'Meta': {'object_name': 'MailingList', 'db_table': "'voting_mailing_list'"},
            'address': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'voting.option': {
            'Meta': {'ordering': "('ballot_position', 'name')", 'object_name': 'Option'},
            'ballot_position': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'result': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'topic': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'options'", 'null': 'True', 'to': "orm['voting.Topic']"}),
            'voters': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'voted_options'", 'symmetrical': 'False', 'through': "orm['voting.Vote']", 'to': "orm['auth.User']"})
        },
        'voting.receipt': {
            'Meta': {'object_name': 'Receipt'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'topic': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'receipts'", 'to': "orm['voting.Topic']"}),
            'vote_key': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'voter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'receipts'", 'to': "orm['auth.User']"})
        },
        'voting.topic': {
            'Meta': {'ordering': "('created',)", 'object_name': 'Topic'},
            'agenda': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'topics'", 'to': "orm['voting.Agenda']"}),
            'agenda_items': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'topics'", 'symmetrical': 'False', 'to': "orm['voting.AgendaItem']"}),
            'author': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'topics'", 'to': "orm['auth.User']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deadline': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invalid': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'open': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'result_calculated': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'second': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'seconded_topics'", 'null': 'True', 'to': "orm['auth.User']"}),
            'subscribers': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'subscribed_topics'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'text': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'token': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'vote_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'topics'", 'to': "orm['voting.VoteType']"})
        },
        'voting.vote': {
            'Meta': {'object_name': 'Vote'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'option': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'votes'", 'to': "orm['voting.Option']"}),
            'rank': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'null': 'True', 'blank': 'True'}),
            'voter': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'votes'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'voting.votetype': {
            'Meta': {'object_name': 'VoteType', 'db_table': "'voting_vote_type'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'max_votes': ('django.db.models.fields.IntegerField', [], {'default': '1', 'null': 'True', 'blank': 'True'}),
            'max_winners': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['voting']