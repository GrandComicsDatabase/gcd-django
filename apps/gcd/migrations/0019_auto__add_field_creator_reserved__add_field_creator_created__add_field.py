# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Creator.reserved'
        db.add_column('gcd_creator', 'reserved',
                      self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True),
                      keep_default=False)

        # Adding field 'Creator.created'
        db.add_column('gcd_creator', 'created',
                      self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 8, 14, 0, 0), auto_now_add=True, blank=True),
                      keep_default=False)

        # Adding field 'Creator.modified'
        db.add_column('gcd_creator', 'modified',
                      self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2015, 8, 14, 0, 0), auto_now=True, blank=True),
                      keep_default=False)

        # Adding field 'Creator.deleted'
        db.add_column('gcd_creator', 'deleted',
                      self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True),
                      keep_default=False)

        # Deleting field 'DeathProvinceSource.source_name'
        db.delete_column('gcd_deathprovincesource', 'source_name')

        # Adding field 'DeathProvinceSource.source_description'
        db.add_column('gcd_deathprovincesource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'DeathMonthSource.source_name'
        db.delete_column('gcd_deathmonthsource', 'source_name')

        # Adding field 'DeathMonthSource.source_description'
        db.add_column('gcd_deathmonthsource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'BirthCitySource.source_name'
        db.delete_column('gcd_birthcitysource', 'source_name')

        # Adding field 'BirthCitySource.source_description'
        db.add_column('gcd_birthcitysource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'BirthProvinceSource.source_name'
        db.delete_column('gcd_birthprovincesource', 'source_name')

        # Adding field 'BirthProvinceSource.source_description'
        db.add_column('gcd_birthprovincesource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'BioSource.source_name'
        db.delete_column('gcd_biosource', 'source_name')

        # Adding field 'BioSource.source_description'
        db.add_column('gcd_biosource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)


        # Changing field 'NameType.type'
        db.alter_column('gcd_nametype', 'type', self.gf('django.db.models.fields.CharField')(max_length=50, null=True))
        # Deleting field 'BirthYearSource.source_name'
        db.delete_column('gcd_birthyearsource', 'source_name')

        # Adding field 'BirthYearSource.source_description'
        db.add_column('gcd_birthyearsource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'BirthCountrySource.source_name'
        db.delete_column('gcd_birthcountrysource', 'source_name')

        # Adding field 'BirthCountrySource.source_description'
        db.add_column('gcd_birthcountrysource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'DeathCitySource.source_name'
        db.delete_column('gcd_deathcitysource', 'source_name')

        # Adding field 'DeathCitySource.source_description'
        db.add_column('gcd_deathcitysource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'PortraitSource.source_name'
        db.delete_column('gcd_portraitsource', 'source_name')

        # Adding field 'PortraitSource.source_description'
        db.add_column('gcd_portraitsource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)


        # Changing field 'CreatorDegreeDetail.school'
        db.alter_column('gcd_creatordegreedetail', 'school_id', self.gf('django.db.models.fields.related.ForeignKey')(null=True, to=orm['gcd.School']))
        # Deleting field 'DeathDateSource.source_name'
        db.delete_column('gcd_deathdatesource', 'source_name')

        # Adding field 'DeathDateSource.source_description'
        db.add_column('gcd_deathdatesource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'DeathYearSource.source_name'
        db.delete_column('gcd_deathyearsource', 'source_name')

        # Adding field 'DeathYearSource.source_description'
        db.add_column('gcd_deathyearsource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'DeathCountrySource.source_name'
        db.delete_column('gcd_deathcountrysource', 'source_name')

        # Adding field 'DeathCountrySource.source_description'
        db.add_column('gcd_deathcountrysource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'NameSource.source_name'
        db.delete_column('gcd_namesource', 'source_name')

        # Adding field 'NameSource.source_description'
        db.add_column('gcd_namesource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'BirthDateSource.source_name'
        db.delete_column('gcd_birthdatesource', 'source_name')

        # Adding field 'BirthDateSource.source_description'
        db.add_column('gcd_birthdatesource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'BirthMonthSource.source_name'
        db.delete_column('gcd_birthmonthsource', 'source_name')

        # Adding field 'BirthMonthSource.source_description'
        db.add_column('gcd_birthmonthsource', 'source_description',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Creator.reserved'
        db.delete_column('gcd_creator', 'reserved')

        # Deleting field 'Creator.created'
        db.delete_column('gcd_creator', 'created')

        # Deleting field 'Creator.modified'
        db.delete_column('gcd_creator', 'modified')

        # Deleting field 'Creator.deleted'
        db.delete_column('gcd_creator', 'deleted')

        # Adding field 'DeathProvinceSource.source_name'
        db.add_column('gcd_deathprovincesource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'DeathProvinceSource.source_description'
        db.delete_column('gcd_deathprovincesource', 'source_description')

        # Adding field 'DeathMonthSource.source_name'
        db.add_column('gcd_deathmonthsource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'DeathMonthSource.source_description'
        db.delete_column('gcd_deathmonthsource', 'source_description')

        # Adding field 'BirthCitySource.source_name'
        db.add_column('gcd_birthcitysource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BirthCitySource.source_description'
        db.delete_column('gcd_birthcitysource', 'source_description')

        # Adding field 'BirthProvinceSource.source_name'
        db.add_column('gcd_birthprovincesource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BirthProvinceSource.source_description'
        db.delete_column('gcd_birthprovincesource', 'source_description')

        # Adding field 'BioSource.source_name'
        db.add_column('gcd_biosource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BioSource.source_description'
        db.delete_column('gcd_biosource', 'source_description')


        # Changing field 'NameType.type'
        db.alter_column('gcd_nametype', 'type', self.gf('django.db.models.fields.CharField')(default=None, max_length=50))
        # Adding field 'BirthYearSource.source_name'
        db.add_column('gcd_birthyearsource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BirthYearSource.source_description'
        db.delete_column('gcd_birthyearsource', 'source_description')

        # Adding field 'BirthCountrySource.source_name'
        db.add_column('gcd_birthcountrysource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BirthCountrySource.source_description'
        db.delete_column('gcd_birthcountrysource', 'source_description')

        # Adding field 'DeathCitySource.source_name'
        db.add_column('gcd_deathcitysource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'DeathCitySource.source_description'
        db.delete_column('gcd_deathcitysource', 'source_description')

        # Adding field 'PortraitSource.source_name'
        db.add_column('gcd_portraitsource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'PortraitSource.source_description'
        db.delete_column('gcd_portraitsource', 'source_description')


        # Changing field 'CreatorDegreeDetail.school'
        db.alter_column('gcd_creatordegreedetail', 'school_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['gcd.School']))
        # Adding field 'DeathDateSource.source_name'
        db.add_column('gcd_deathdatesource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'DeathDateSource.source_description'
        db.delete_column('gcd_deathdatesource', 'source_description')

        # Adding field 'DeathYearSource.source_name'
        db.add_column('gcd_deathyearsource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'DeathYearSource.source_description'
        db.delete_column('gcd_deathyearsource', 'source_description')

        # Adding field 'DeathCountrySource.source_name'
        db.add_column('gcd_deathcountrysource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'DeathCountrySource.source_description'
        db.delete_column('gcd_deathcountrysource', 'source_description')

        # Adding field 'NameSource.source_name'
        db.add_column('gcd_namesource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'NameSource.source_description'
        db.delete_column('gcd_namesource', 'source_description')

        # Adding field 'BirthDateSource.source_name'
        db.add_column('gcd_birthdatesource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BirthDateSource.source_description'
        db.delete_column('gcd_birthdatesource', 'source_description')

        # Adding field 'BirthMonthSource.source_name'
        db.add_column('gcd_birthmonthsource', 'source_name',
                      self.gf('django.db.models.fields.TextField')(default=None),
                      keep_default=False)

        # Deleting field 'BirthMonthSource.source_description'
        db.delete_column('gcd_birthmonthsource', 'source_description')


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
        'gcd.artinfluence': {
            'Meta': {'object_name': 'ArtInfluence'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'influence_link': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'exist_influencer'", 'null': 'True', 'to': "orm['gcd.Creator']"}),
            'influence_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'influence_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'influencesource'", 'symmetrical': 'False', 'to': "orm['gcd.SourceType']"}),
            'is_self_identify': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'self_identify_influences_doc': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'gcd.award': {
            'Meta': {'ordering': "('award_year',)", 'object_name': 'Award'},
            'award_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'award_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'awardsource'", 'symmetrical': 'False', 'to': "orm['gcd.SourceType']"}),
            'award_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'award_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'gcd.biosource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BioSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbiosource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbiosourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.birthcitysource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthCitySource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthcitysource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthcitysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.birthcountrysource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthCountrySource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthcountrysource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthcountrysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.birthdatesource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthDateSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthdatesource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthdatesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.birthmonthsource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthMonthSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthmonthsource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthmonthsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.birthprovincesource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthProvinceSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthprovincesource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthprovincesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.birthyearsource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthYearSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthyearsource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorbirthyearsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.brand': {
            'Meta': {'ordering': "['name']", 'object_name': 'Brand'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'group': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['gcd.BrandGroup']", 'symmetrical': 'False', 'db_table': "'gcd_brand_emblem_group'", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issue_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Publisher']", 'null': 'True', 'blank': 'True'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.brandgroup': {
            'Meta': {'ordering': "['name']", 'object_name': 'BrandGroup', 'db_table': "'gcd_brand_group'"},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issue_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Publisher']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.branduse': {
            'Meta': {'object_name': 'BrandUse', 'db_table': "'gcd_brand_use'"},
            'created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'emblem': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'in_use'", 'to': "orm['gcd.Brand']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Publisher']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.country': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Country'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'gcd.countstats': {
            'Meta': {'object_name': 'CountStats', 'db_table': "'gcd_count_stats'"},
            'count': ('django.db.models.fields.IntegerField', [], {}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Language']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'db_index': 'True'})
        },
        'gcd.cover': {
            'Meta': {'ordering': "['issue']", 'object_name': 'Cover'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'front_bottom': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'front_left': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'front_right': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'front_top': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_wraparound': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Issue']"}),
            'last_upload': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'limit_display': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.creator': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Creator'},
            'bio': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'bio_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'biosource'", 'symmetrical': 'False', 'through': "orm['gcd.BioSource']", 'to': "orm['gcd.SourceType']"}),
            'birth_city': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'birth_city_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'birthcitysource'", 'symmetrical': 'False', 'through': "orm['gcd.BirthCitySource']", 'to': "orm['gcd.SourceType']"}),
            'birth_city_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_country': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'birth_country'", 'null': 'True', 'to': "orm['gcd.Country']"}),
            'birth_country_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'birthcountrysource'", 'symmetrical': 'False', 'through': "orm['gcd.BirthCountrySource']", 'to': "orm['gcd.SourceType']"}),
            'birth_country_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_date': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'birth_date_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'birthdatesource'", 'symmetrical': 'False', 'through': "orm['gcd.BirthDateSource']", 'to': "orm['gcd.SourceType']"}),
            'birth_date_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_month': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'birth_month_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'birthmonthsource'", 'symmetrical': 'False', 'through': "orm['gcd.BirthMonthSource']", 'to': "orm['gcd.SourceType']"}),
            'birth_month_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_province': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'birth_province_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'birthprovincesource'", 'symmetrical': 'False', 'through': "orm['gcd.BirthProvinceSource']", 'to': "orm['gcd.SourceType']"}),
            'birth_province_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'birth_year_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'birthyearsource'", 'symmetrical': 'False', 'through': "orm['gcd.BirthYearSource']", 'to': "orm['gcd.SourceType']"}),
            'birth_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 8, 14, 0, 0)', 'auto_now_add': 'True', 'blank': 'True'}),
            'death_city': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'death_city_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deathcitysource'", 'symmetrical': 'False', 'through': "orm['gcd.DeathCitySource']", 'to': "orm['gcd.SourceType']"}),
            'death_city_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_country': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'death_country'", 'null': 'True', 'to': "orm['gcd.Country']"}),
            'death_country_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deathcountrysource'", 'symmetrical': 'False', 'through': "orm['gcd.DeathCountrySource']", 'to': "orm['gcd.SourceType']"}),
            'death_country_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_date': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'death_date_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deathdatesource'", 'symmetrical': 'False', 'through': "orm['gcd.DeathDateSource']", 'to': "orm['gcd.SourceType']"}),
            'death_date_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_month': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'death_month_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deathmonthsource'", 'symmetrical': 'False', 'through': "orm['gcd.DeathMonthSource']", 'to': "orm['gcd.SourceType']"}),
            'death_month_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_province': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'death_province_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deathprovincesource'", 'symmetrical': 'False', 'through': "orm['gcd.DeathProvinceSource']", 'to': "orm['gcd.SourceType']"}),
            'death_province_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'death_year_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deathyearsource'", 'symmetrical': 'False', 'through': "orm['gcd.DeathYearSource']", 'to': "orm['gcd.SourceType']"}),
            'death_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'degrees': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'degreeinformation'", 'symmetrical': 'False', 'through': "orm['gcd.CreatorDegreeDetail']", 'to': "orm['gcd.Degree']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2015, 8, 14, 0, 0)', 'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'namesource'", 'symmetrical': 'False', 'through': "orm['gcd.NameSource']", 'to': "orm['gcd.SourceType']"}),
            'name_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.NameType']"}),
            'notes': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'portrait': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'portrait_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'portraitsource'", 'symmetrical': 'False', 'through': "orm['gcd.PortraitSource']", 'to': "orm['gcd.SourceType']"}),
            'related_person': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['gcd.Creator']", 'through': "orm['gcd.NameRelation']", 'symmetrical': 'False'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'sample_scan': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'schools': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'schoolinformation'", 'symmetrical': 'False', 'through': "orm['gcd.CreatorSchoolDetail']", 'to': "orm['gcd.School']"}),
            'whos_who': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'gcd.creatordegreedetail': {
            'Meta': {'ordering': "('degree_year',)", 'object_name': 'CreatorDegreeDetail'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creator_degree'", 'to': "orm['gcd.Creator']"}),
            'degree': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'degreedetails'", 'to': "orm['gcd.Degree']"}),
            'degree_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'degree_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'school': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'schooldetails'", 'null': 'True', 'to': "orm['gcd.School']"})
        },
        'gcd.creatorschooldetail': {
            'Meta': {'ordering': "('school_year_began', 'school_year_ended')", 'object_name': 'CreatorSchoolDetail'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creator_school'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'school': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'school_details'", 'to': "orm['gcd.School']"}),
            'school_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'schoolsource'", 'symmetrical': 'False', 'to': "orm['gcd.SourceType']"}),
            'school_year_began': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'school_year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'school_year_ended': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'school_year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'gcd.deathcitysource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathCitySource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathcitysource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathcitysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.deathcountrysource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathCountrySource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathcountrysource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathcountrysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.deathdatesource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathDateSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathdatesource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathdatesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.deathmonthsource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathMonthSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathmonthsource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathmonthsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.deathprovincesource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathProvinceSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathprovincesource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathprovincesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.deathyearsource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathYearSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathyearsource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordeathyearsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.degree': {
            'Meta': {'ordering': "('degree_name',)", 'object_name': 'Degree'},
            'degree_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'gcd.error': {
            'Meta': {'object_name': 'Error'},
            'error_key': ('django.db.models.fields.CharField', [], {'max_length': '40', 'primary_key': 'True'}),
            'error_text': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'is_safe': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'gcd.image': {
            'Meta': {'object_name': 'Image'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_file': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'null': 'True', 'blank': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.ImageType']"})
        },
        'gcd.imagetype': {
            'Meta': {'object_name': 'ImageType', 'db_table': "'gcd_image_type'"},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'}),
            'unique': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'gcd.impgrant': {
            'Meta': {'object_name': 'ImpGrant', 'db_table': "'gcd_imp_grant'"},
            'grant_type': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imps': ('django.db.models.fields.IntegerField', [], {}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imp_grant_set'", 'to': "orm['gcd.Indexer']"}),
            'notes': ('django.db.models.fields.TextField', [], {})
        },
        'gcd.indexcredit': {
            'Meta': {'object_name': 'IndexCredit', 'db_table': "'gcd_series_indexers'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'index_credit_set'", 'to': "orm['gcd.Indexer']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'run': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'series': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'index_credit_set'", 'to': "orm['gcd.Series']"})
        },
        'gcd.indexer': {
            'Meta': {'ordering': "['user__last_name', 'user__first_name']", 'object_name': 'Indexer'},
            'collapse_compare_view': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indexers'", 'to': "orm['gcd.Country']"}),
            'deceased': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'from_where': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imps': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'interests': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'is_banned': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'is_new': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'issue_detail': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'languages': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'indexers'", 'symmetrical': 'False', 'db_table': "'gcd_indexer_languages'", 'to': "orm['gcd.Language']"}),
            'max_ongoing': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'max_reservations': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'mentor': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'mentees'", 'null': 'True', 'to': "orm['auth.User']"}),
            'notify_on_approve': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'opt_in_email': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'registration_expires': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'registration_key': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True', 'db_index': 'True'}),
            'show_wiki_links': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        },
        'gcd.indiciapublisher': {
            'Meta': {'ordering': "['name']", 'object_name': 'IndiciaPublisher', 'db_table': "'gcd_indicia_publisher'"},
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_surrogate': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'issue_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Publisher']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.issue': {
            'Meta': {'ordering': "['series', 'sort_code']", 'unique_together': "(('series', 'sort_code'),)", 'object_name': 'Issue'},
            'barcode': ('django.db.models.fields.CharField', [], {'max_length': '38', 'db_index': 'True'}),
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Brand']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'display_volume_with_number': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'editing': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indicia_frequency': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'indicia_pub_not_printed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'indicia_publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.IndiciaPublisher']", 'null': 'True'}),
            'is_indexed': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'isbn': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'key_date': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'no_barcode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_brand': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_editing': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_indicia_frequency': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_isbn': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_rating': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_title': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_volume': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'on_sale_date': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'on_sale_date_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'page_count': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '3'}),
            'page_count_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'price': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'publication_date': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'rating': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'db_index': 'True'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'series': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Series']"}),
            'sort_code': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'valid_isbn': ('django.db.models.fields.CharField', [], {'max_length': '13', 'db_index': 'True'}),
            'variant_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'variant_of': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'variant_set'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'volume': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        },
        'gcd.issuereprint': {
            'Meta': {'object_name': 'IssueReprint', 'db_table': "'gcd_issue_reprint'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_issue_reprints'", 'to': "orm['gcd.Issue']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_issue_reprints'", 'to': "orm['gcd.Issue']"})
        },
        'gcd.language': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'gcd.membership': {
            'Meta': {'ordering': "('membership_type',)", 'object_name': 'Membership'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'membership_begin_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'membership_begin_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'membership_end_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'membership_end_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'membership_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'membershipsource'", 'symmetrical': 'False', 'to': "orm['gcd.SourceType']"}),
            'membership_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.MembershipType']"}),
            'organization_name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'gcd.membershiptype': {
            'Meta': {'object_name': 'MembershipType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'gcd.migrationstorystatus': {
            'Meta': {'object_name': 'MigrationStoryStatus', 'db_table': "'gcd_migration_story_status'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'reprint_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'reprint_needs_inspection': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'reprint_original_notes': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'story': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'migration_status'", 'unique': 'True', 'to': "orm['gcd.Story']"})
        },
        'gcd.namerelation': {
            'Meta': {'ordering': "('gcd_official_name', 'rel_type', 'to_name')", 'object_name': 'NameRelation'},
            'gcd_official_name': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'gcd_official_name'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rel_source': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['gcd.SourceType']", 'symmetrical': 'False'}),
            'rel_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relation_type'", 'to': "orm['gcd.RelationType']"}),
            'to_name': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_name'", 'to': "orm['gcd.Creator']"})
        },
        'gcd.namesource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'NameSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatornamesource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'namesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.nametype': {
            'Meta': {'ordering': "('type',)", 'object_name': 'NameType'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'})
        },
        'gcd.noncomicwork': {
            'Meta': {'ordering': "('publication_title', 'employer_name', 'work_type')", 'object_name': 'NonComicWork'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Creator']"}),
            'employer_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'publication_title': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'work_notes': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'work_role': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.NonComicWorkRole']"}),
            'work_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'worksource'", 'symmetrical': 'False', 'to': "orm['gcd.SourceType']"}),
            'work_title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'work_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.NonComicWorkType']"})
        },
        'gcd.noncomicworklink': {
            'Meta': {'object_name': 'NonComicWorkLink'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '255'}),
            'non_comic_work': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.NonComicWork']"})
        },
        'gcd.noncomicworkrole': {
            'Meta': {'object_name': 'NonComicWorkRole'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'role_name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'gcd.noncomicworktype': {
            'Meta': {'object_name': 'NonComicWorkType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'gcd.noncomicworkyear': {
            'Meta': {'ordering': "('work_year',)", 'object_name': 'NonComicWorkYear'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'non_comic_work': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.NonComicWork']"}),
            'work_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'work_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'gcd.portraitsource': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'PortraitSource'},
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorportraitsource'", 'to': "orm['gcd.Creator']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorportraitsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'gcd.publisher': {
            'Meta': {'ordering': "['name']", 'object_name': 'Publisher'},
            'brand_count': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imprint_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'indicia_publisher_count': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'is_master': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'issue_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imprint_set'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'series_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.recentindexedissue': {
            'Meta': {'object_name': 'RecentIndexedIssue', 'db_table': "'gcd_recent_indexed_issue'"},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Issue']"}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Language']", 'null': 'True'})
        },
        'gcd.relationtype': {
            'Meta': {'ordering': "('type',)", 'object_name': 'RelationType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'gcd.reprint': {
            'Meta': {'object_name': 'Reprint'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_reprints'", 'to': "orm['gcd.Story']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_reprints'", 'to': "orm['gcd.Story']"})
        },
        'gcd.reprintfromissue': {
            'Meta': {'object_name': 'ReprintFromIssue', 'db_table': "'gcd_reprint_from_issue'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_reprints'", 'to': "orm['gcd.Issue']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_issue_reprints'", 'to': "orm['gcd.Story']"})
        },
        'gcd.reprinttoissue': {
            'Meta': {'object_name': 'ReprintToIssue', 'db_table': "'gcd_reprint_to_issue'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_issue_reprints'", 'to': "orm['gcd.Story']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_reprints'", 'to': "orm['gcd.Issue']"})
        },
        'gcd.reservation': {
            'Meta': {'object_name': 'Reservation'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'expires': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reservation_set'", 'to': "orm['gcd.Indexer']"}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reservation_set'", 'to': "orm['gcd.Issue']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        },
        'gcd.school': {
            'Meta': {'ordering': "('school_name',)", 'object_name': 'School'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'school_name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'gcd.series': {
            'Meta': {'ordering': "['sort_name', 'year_began']", 'object_name': 'Series'},
            'binding': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'color': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'dimensions': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'first_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'first_issue_series_set'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'format': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'has_barcode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_gallery': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'has_indicia_frequency': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_isbn': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_issue_title': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_rating': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_volume': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_comics_publication': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_current': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'is_singleton': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'issue_count': ('django.db.models.fields.IntegerField', [], {}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Language']"}),
            'last_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'last_issue_series_set'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'open_reserve': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'paper_stock': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'publication_dates': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'publication_notes': ('django.db.models.fields.TextField', [], {}),
            'publication_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.SeriesPublicationType']", 'null': 'True', 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Publisher']"}),
            'publishing_format': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'sort_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'tracking_notes': ('django.db.models.fields.TextField', [], {}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'gcd.seriesbond': {
            'Meta': {'object_name': 'SeriesBond', 'db_table': "'gcd_series_bond'"},
            'bond_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.SeriesBondType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_series_bond'", 'to': "orm['gcd.Series']"}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_series_issue_bond'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_series_bond'", 'to': "orm['gcd.Series']"}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_series_issue_bond'", 'null': 'True', 'to': "orm['gcd.Issue']"})
        },
        'gcd.seriesbondtype': {
            'Meta': {'object_name': 'SeriesBondType', 'db_table': "'gcd_series_bond_type'"},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'gcd.seriespublicationtype': {
            'Meta': {'ordering': "['name']", 'object_name': 'SeriesPublicationType', 'db_table': "'gcd_series_publication_type'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {})
        },
        'gcd.sourcetype': {
            'Meta': {'ordering': "('type',)", 'object_name': 'SourceType'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'gcd.story': {
            'Meta': {'ordering': "['sequence_number']", 'object_name': 'Story'},
            'characters': ('django.db.models.fields.TextField', [], {}),
            'colors': ('django.db.models.fields.TextField', [], {}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'editing': ('django.db.models.fields.TextField', [], {}),
            'feature': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'genre': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'inks': ('django.db.models.fields.TextField', [], {}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Issue']"}),
            'job_number': ('django.db.models.fields.CharField', [], {'max_length': '25'}),
            'letters': ('django.db.models.fields.TextField', [], {}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'no_colors': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_editing': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_inks': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_letters': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_pencils': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'no_script': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'page_count': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '3', 'db_index': 'True'}),
            'page_count_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'pencils': ('django.db.models.fields.TextField', [], {}),
            'reprint_notes': ('django.db.models.fields.TextField', [], {}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'script': ('django.db.models.fields.TextField', [], {}),
            'sequence_number': ('django.db.models.fields.IntegerField', [], {}),
            'synopsis': ('django.db.models.fields.TextField', [], {}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'title_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.StoryType']"})
        },
        'gcd.storytype': {
            'Meta': {'ordering': "['sort_code']", 'object_name': 'StoryType', 'db_table': "'gcd_story_type'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'}),
            'sort_code': ('django.db.models.fields.IntegerField', [], {'unique': 'True'})
        },
        'taggit.tag': {
            'Meta': {'object_name': 'Tag'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '100'})
        },
        'taggit.taggeditem': {
            'Meta': {'object_name': 'TaggedItem'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'taggit_taggeditem_tagged_items'", 'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'tag': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'taggit_taggeditem_items'", 'to': "orm['taggit.Tag']"})
        }
    }

    complete_apps = ['gcd']