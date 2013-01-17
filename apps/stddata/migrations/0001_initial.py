# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Currency'
        db.create_table('stddata_currency', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=3)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, db_index=True)),
            ('is_decimal', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('stddata', ['Currency'])

        # Adding model 'Date'
        db.create_table('stddata_date', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('year', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=4, blank=True)),
            ('month', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=2, blank=True)),
            ('day', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=2, blank=True)),
            ('year_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('month_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('day_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('stddata', ['Date'])


    def backwards(self, orm):
        # Deleting model 'Currency'
        db.delete_table('stddata_currency')

        # Deleting model 'Date'
        db.delete_table('stddata_date')


    models = {
        'stddata.currency': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Currency'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '3'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_decimal': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        'stddata.date': {
            'Meta': {'ordering': "('year', 'month', 'day')", 'object_name': 'Date'},
            'day': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '2', 'blank': 'True'}),
            'day_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'month': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '2', 'blank': 'True'}),
            'month_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '4', 'blank': 'True'}),
            'year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['stddata']