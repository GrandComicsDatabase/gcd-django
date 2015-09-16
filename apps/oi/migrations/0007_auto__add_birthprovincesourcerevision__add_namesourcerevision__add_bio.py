# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'BirthProvinceSourceRevision'
        db.create_table('oi_birthprovincesourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='birthprovincesourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('birth_province_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_birth_province_source', null=True, to=orm['gcd.BirthProvinceSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthprovincesource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthprovincesourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BirthProvinceSourceRevision'])

        # Adding model 'NameSourceRevision'
        db.create_table('oi_namesourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='namesourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('name_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_name_source', null=True, to=orm['gcd.NameSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatornamesource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_namesourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['NameSourceRevision'])

        # Adding model 'BioSourceRevision'
        db.create_table('oi_biosourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='biosourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('bio_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_bio_source', null=True, to=orm['gcd.BioSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbiosource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbiosourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BioSourceRevision'])

        # Adding model 'BirthCountrySourceRevision'
        db.create_table('oi_birthcountrysourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='birthcountrysourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('birth_country_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_birth_country_source', null=True, to=orm['gcd.BirthCountrySource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthcountrysource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthcountrysourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BirthCountrySourceRevision'])

        # Adding model 'BirthDateSourceRevision'
        db.create_table('oi_birthdatesourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='birthdatesourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('birth_date_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_birth_date_source', null=True, to=orm['gcd.BirthDateSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthdatesource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthdatesourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BirthDateSourceRevision'])

        # Adding model 'BirthYearSourceRevision'
        db.create_table('oi_birthyearsourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='birthyearsourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('birth_year_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_birth_year_source', null=True, to=orm['gcd.BirthYearSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthyearsource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthyearsourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BirthYearSourceRevision'])

        # Adding model 'RelationTypeRevision'
        db.create_table('oi_relationtyperevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='relationtyperevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('relation_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_relation_type', null=True, to=orm['gcd.RelationType'])),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=50)),
        ))
        db.send_create_signal('oi', ['RelationTypeRevision'])

        # Adding model 'NameRelationRevision'
        db.create_table('oi_namerelation_revision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='namerelationrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('name_relation', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_name_relation', null=True, to=orm['gcd.NameRelation'])),
            ('gcd_official_name', self.gf('django.db.models.fields.related.ForeignKey')(related_name='creator_revise_gcd_official_name', to=orm['oi.CreatorRevision'])),
            ('to_name', self.gf('django.db.models.fields.related.ForeignKey')(related_name='creator_revise_to_name', to=orm['oi.CreatorRevision'])),
            ('rel_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='creator_revise_relation_type', to=orm['oi.RelationTypeRevision'])),
            ('rel_source', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['NameRelationRevision'])

        # Adding model 'DeathCountrySourceRevision'
        db.create_table('oi_deathcountrysourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deathcountrysourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('death_country_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_death_country_source', null=True, to=orm['gcd.DeathCountrySource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathcountrysource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathcountrysourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['DeathCountrySourceRevision'])

        # Adding model 'DeathProvinceSourceRevision'
        db.create_table('oi_deathprovincesourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deathprovincesourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('death_province_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_death_province_source', null=True, to=orm['gcd.DeathProvinceSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathprovincesource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathprovincesourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['DeathProvinceSourceRevision'])

        # Adding model 'DeathDateSourceRevision'
        db.create_table('oi_deathdatesourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deathdatesourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('death_date_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_death_date_source', null=True, to=orm['gcd.DeathDateSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathdatesource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathdatesourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['DeathDateSourceRevision'])

        # Adding model 'DeathYearSourceRevision'
        db.create_table('oi_deathyearsourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deathyearsourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('death_year_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_death_year_source', null=True, to=orm['gcd.DeathYearSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathyearsource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathyearsourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['DeathYearSourceRevision'])

        # Adding model 'PortraitSourceRevision'
        db.create_table('oi_portraitsourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='portraitsourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('portrait_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_portrait_source', null=True, to=orm['gcd.PortraitSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorportraitsource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorportraitsourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['PortraitSourceRevision'])

        # Adding model 'DeathCitySourceRevision'
        db.create_table('oi_deathcitysourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deathcitysourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('death_city_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_death_city_source', null=True, to=orm['gcd.DeathCitySource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathcitysource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathcitysourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['DeathCitySourceRevision'])

        # Adding model 'CreatorSchoolDetailRevision'
        db.create_table('oi_creatorschooldetailrevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='creatorschooldetailrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('creator_school_detail', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creator_school_detail', null=True, to=orm['gcd.CreatorSchoolDetail'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creator_school', to=orm['oi.CreatorRevision'])),
            ('school', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_school_details', to=orm['gcd.School'])),
            ('school_year_began', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('school_year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('school_year_ended', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('school_year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('oi', ['CreatorSchoolDetailRevision'])

        # Adding M2M table for field school_source on 'CreatorSchoolDetailRevision'
        m2m_table_name = db.shorten_name('oi_creatorschooldetailrevision_school_source')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('creatorschooldetailrevision', models.ForeignKey(orm['oi.creatorschooldetailrevision'], null=False)),
            ('sourcetype', models.ForeignKey(orm['gcd.sourcetype'], null=False))
        ))
        db.create_unique(m2m_table_name, ['creatorschooldetailrevision_id', 'sourcetype_id'])

        # Adding model 'CreatorDegreeDetailRevision'
        db.create_table('oi_creatordegreedetailrevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='creatordegreedetailrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('creater_degree_detail', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creater_degree_detail', null=True, to=orm['gcd.CreatorDegreeDetail'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creator_degree', to=orm['oi.CreatorRevision'])),
            ('school', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_schooldetails', null=True, to=orm['gcd.School'])),
            ('degree', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_degreedetails', to=orm['gcd.Degree'])),
            ('degree_year', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('degree_year_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('oi', ['CreatorDegreeDetailRevision'])

        # Adding model 'BirthMonthSourceRevision'
        db.create_table('oi_birthmonthsourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='birthmonthsourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('birth_month_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_birth_month_source', null=True, to=orm['gcd.BirthMonthSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthmonthsource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthmonthsourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BirthMonthSourceRevision'])

        # Adding model 'DeathMonthSourceRevision'
        db.create_table('oi_deathmonthsourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='deathmonthsourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('death_month_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_death_month_source', null=True, to=orm['gcd.DeathMonthSource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathmonthsource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatordeathmonthsourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['DeathMonthSourceRevision'])

        # Adding model 'CreatorRevision'
        db.create_table('oi_creator_revision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='creatorrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Creator'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('name_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.NameType'])),
            ('birth_year', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('birth_year_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('birth_month', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('birth_month_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('birth_date', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('birth_date_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('death_year', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('death_year_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('death_month', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('death_month_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('death_date', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('death_date_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('whos_who', self.gf('django.db.models.fields.URLField')(default=None, max_length=200, null=True, blank=True)),
            ('birth_country', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='cr_birth_country', null=True, to=orm['gcd.Country'])),
            ('birth_country_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('birth_province', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('birth_province_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('birth_city', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('birth_city_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('death_country', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='cr_death_country', null=True, to=orm['gcd.Country'])),
            ('death_country_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('death_province', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('death_province_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('death_city', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('death_city_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('portrait', self.gf('django.db.models.fields.files.ImageField')(max_length=100)),
            ('bio', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('sample_scan', self.gf('django.db.models.fields.files.FileField')(max_length=100)),
            ('notes', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['CreatorRevision'])

        # Adding model 'BirthCitySourceRevision'
        db.create_table('oi_birthcitysourcerevision', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='birthcitysourcerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('birth_city_source', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_birth_city_source', null=True, to=orm['gcd.BirthCitySource'])),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthcitysource', to=orm['oi.CreatorRevision'])),
            ('source_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cr_creatorbirthcitysourcetype', to=orm['gcd.SourceType'])),
            ('source_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('oi', ['BirthCitySourceRevision'])


    def backwards(self, orm):
        # Deleting model 'BirthProvinceSourceRevision'
        db.delete_table('oi_birthprovincesourcerevision')

        # Deleting model 'NameSourceRevision'
        db.delete_table('oi_namesourcerevision')

        # Deleting model 'BioSourceRevision'
        db.delete_table('oi_biosourcerevision')

        # Deleting model 'BirthCountrySourceRevision'
        db.delete_table('oi_birthcountrysourcerevision')

        # Deleting model 'BirthDateSourceRevision'
        db.delete_table('oi_birthdatesourcerevision')

        # Deleting model 'BirthYearSourceRevision'
        db.delete_table('oi_birthyearsourcerevision')

        # Deleting model 'RelationTypeRevision'
        db.delete_table('oi_relationtyperevision')

        # Deleting model 'NameRelationRevision'
        db.delete_table('oi_namerelation_revision')

        # Deleting model 'DeathCountrySourceRevision'
        db.delete_table('oi_deathcountrysourcerevision')

        # Deleting model 'DeathProvinceSourceRevision'
        db.delete_table('oi_deathprovincesourcerevision')

        # Deleting model 'DeathDateSourceRevision'
        db.delete_table('oi_deathdatesourcerevision')

        # Deleting model 'DeathYearSourceRevision'
        db.delete_table('oi_deathyearsourcerevision')

        # Deleting model 'PortraitSourceRevision'
        db.delete_table('oi_portraitsourcerevision')

        # Deleting model 'DeathCitySourceRevision'
        db.delete_table('oi_deathcitysourcerevision')

        # Deleting model 'CreatorSchoolDetailRevision'
        db.delete_table('oi_creatorschooldetailrevision')

        # Removing M2M table for field school_source on 'CreatorSchoolDetailRevision'
        db.delete_table(db.shorten_name('oi_creatorschooldetailrevision_school_source'))

        # Deleting model 'CreatorDegreeDetailRevision'
        db.delete_table('oi_creatordegreedetailrevision')

        # Deleting model 'BirthMonthSourceRevision'
        db.delete_table('oi_birthmonthsourcerevision')

        # Deleting model 'DeathMonthSourceRevision'
        db.delete_table('oi_deathmonthsourcerevision')

        # Deleting model 'CreatorRevision'
        db.delete_table('oi_creator_revision')

        # Deleting model 'BirthCitySourceRevision'
        db.delete_table('oi_birthcitysourcerevision')


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
        'oi.biosourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BioSourceRevision'},
            'bio_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_bio_source'", 'null': 'True', 'to': "orm['gcd.BioSource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'biosourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbiosource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbiosourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.birthcitysourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthCitySourceRevision'},
            'birth_city_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_birth_city_source'", 'null': 'True', 'to': "orm['gcd.BirthCitySource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'birthcitysourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthcitysource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthcitysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.birthcountrysourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthCountrySourceRevision'},
            'birth_country_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_birth_country_source'", 'null': 'True', 'to': "orm['gcd.BirthCountrySource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'birthcountrysourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthcountrysource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthcountrysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.birthdatesourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthDateSourceRevision'},
            'birth_date_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_birth_date_source'", 'null': 'True', 'to': "orm['gcd.BirthDateSource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'birthdatesourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthdatesource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthdatesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.birthmonthsourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthMonthSourceRevision'},
            'birth_month_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_birth_month_source'", 'null': 'True', 'to': "orm['gcd.BirthMonthSource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'birthmonthsourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthmonthsource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthmonthsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.birthprovincesourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthProvinceSourceRevision'},
            'birth_province_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_birth_province_source'", 'null': 'True', 'to': "orm['gcd.BirthProvinceSource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'birthprovincesourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthprovincesource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthprovincesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.birthyearsourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'BirthYearSourceRevision'},
            'birth_year_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_birth_year_source'", 'null': 'True', 'to': "orm['gcd.BirthYearSource']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'birthyearsourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthyearsource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorbirthyearsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.brandgrouprevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'BrandGroupRevision', 'db_table': "'oi_brand_group_revision'"},
            'brand_group': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.BrandGroup']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'brandgrouprevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'brand_group_revisions'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.brandrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'BrandRevision', 'db_table': "'oi_brand_revision'"},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Brand']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'brandrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'group': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'brand_revisions'", 'symmetrical': 'False', 'to': "orm['gcd.BrandGroup']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'brand_revisions'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.branduserevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'BrandUseRevision', 'db_table': "'oi_brand_use_revision'"},
            'brand_use': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.BrandUse']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'branduserevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'emblem': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'use_revisions'", 'null': 'True', 'to': "orm['gcd.Brand']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255', 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'brand_use_revisions'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.changeset': {
            'Meta': {'object_name': 'Changeset'},
            'along_with': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'changesets_assisting'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'approver': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'approved_changeset'", 'null': 'True', 'to': "orm['auth.User']"}),
            'change_type': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imps': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'changesets'", 'to': "orm['auth.User']"}),
            'migrated': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'on_behalf_of': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'changesets_source'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'state': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        },
        'oi.changesetcomment': {
            'Meta': {'ordering': "['created']", 'object_name': 'ChangesetComment', 'db_table': "'oi_changeset_comment'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': "orm['oi.Changeset']"}),
            'commenter': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'new_state': ('django.db.models.fields.IntegerField', [], {}),
            'old_state': ('django.db.models.fields.IntegerField', [], {}),
            'revision_id': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {})
        },
        'oi.coverrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'CoverRevision', 'db_table': "'oi_cover_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'coverrevisions'", 'to': "orm['oi.Changeset']"}),
            'cover': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Cover']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'file_source': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'front_bottom': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'front_left': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'front_right': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'front_top': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_replacement': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_wraparound': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cover_revisions'", 'to': "orm['gcd.Issue']"}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'})
        },
        'oi.creatordegreedetailrevision': {
            'Meta': {'ordering': "('degree_year',)", 'object_name': 'CreatorDegreeDetailRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatordegreedetailrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creater_degree_detail': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creater_degree_detail'", 'null': 'True', 'to': "orm['gcd.CreatorDegreeDetail']"}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creator_degree'", 'to': "orm['oi.CreatorRevision']"}),
            'degree': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_degreedetails'", 'to': "orm['gcd.Degree']"}),
            'degree_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'degree_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'school': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_schooldetails'", 'null': 'True', 'to': "orm['gcd.School']"})
        },
        'oi.creatorrevision': {
            'Meta': {'ordering': "['created']", 'object_name': 'CreatorRevision', 'db_table': "'oi_creator_revision'"},
            'bio': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'bio_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_biosource'", 'symmetrical': 'False', 'through': "orm['oi.BioSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_city': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'birth_city_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_birthcitysource'", 'symmetrical': 'False', 'through': "orm['oi.BirthCitySourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_city_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_country': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'cr_birth_country'", 'null': 'True', 'to': "orm['gcd.Country']"}),
            'birth_country_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_birthcountrysource'", 'symmetrical': 'False', 'through': "orm['oi.BirthCountrySourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_country_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_date': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'birth_date_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_birthdatesource'", 'symmetrical': 'False', 'through': "orm['oi.BirthDateSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_date_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_month': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'birth_month_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_birthmonthsource'", 'symmetrical': 'False', 'through': "orm['oi.BirthMonthSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_month_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_province': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'birth_province_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_birthprovincesource'", 'symmetrical': 'False', 'through': "orm['oi.BirthProvinceSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_province_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'birth_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'birth_year_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_birthyearsource'", 'symmetrical': 'False', 'through': "orm['oi.BirthYearSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'birth_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Creator']"}),
            'death_city': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'death_city_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_deathcitysource'", 'symmetrical': 'False', 'through': "orm['oi.DeathCitySourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'death_city_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_country': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'cr_death_country'", 'null': 'True', 'to': "orm['gcd.Country']"}),
            'death_country_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_deathcountrysource'", 'symmetrical': 'False', 'through': "orm['oi.DeathCountrySourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'death_country_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_date': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'death_date_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_deathdatesource'", 'symmetrical': 'False', 'through': "orm['oi.DeathDateSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'death_date_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_month': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'death_month_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_deathmonthsource'", 'symmetrical': 'False', 'through': "orm['oi.DeathMonthSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'death_month_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_province': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'death_province_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_deathprovincesource'", 'symmetrical': 'False', 'through': "orm['oi.DeathProvinceSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'death_province_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'death_year': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'death_year_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_deathyearsource'", 'symmetrical': 'False', 'through': "orm['oi.DeathYearSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'death_year_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'degrees': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_degreeinformation'", 'symmetrical': 'False', 'through': "orm['oi.CreatorDegreeDetailRevision']", 'to': "orm['gcd.Degree']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_namesource'", 'symmetrical': 'False', 'through': "orm['oi.NameSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'name_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.NameType']"}),
            'notes': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'portrait': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'portrait_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_portraitsource'", 'symmetrical': 'False', 'through': "orm['oi.PortraitSourceRevision']", 'to': "orm['gcd.SourceType']"}),
            'related_person': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['oi.CreatorRevision']", 'through': "orm['oi.NameRelationRevision']", 'symmetrical': 'False'}),
            'sample_scan': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'schools': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_schoolinformation'", 'symmetrical': 'False', 'through': "orm['oi.CreatorSchoolDetailRevision']", 'to': "orm['gcd.School']"}),
            'whos_who': ('django.db.models.fields.URLField', [], {'default': 'None', 'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'oi.creatorschooldetailrevision': {
            'Meta': {'ordering': "('school_year_began', 'school_year_ended')", 'object_name': 'CreatorSchoolDetailRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creatorschooldetailrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creator_school'", 'to': "orm['oi.CreatorRevision']"}),
            'creator_school_detail': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creator_school_detail'", 'null': 'True', 'to': "orm['gcd.CreatorSchoolDetail']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'school': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_school_details'", 'to': "orm['gcd.School']"}),
            'school_source': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'cr_schoolsource'", 'symmetrical': 'False', 'to': "orm['gcd.SourceType']"}),
            'school_year_began': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'school_year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'school_year_ended': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'school_year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.deathcitysourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathCitySourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deathcitysourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathcitysource'", 'to': "orm['oi.CreatorRevision']"}),
            'death_city_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_death_city_source'", 'null': 'True', 'to': "orm['gcd.DeathCitySource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathcitysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.deathcountrysourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathCountrySourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deathcountrysourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathcountrysource'", 'to': "orm['oi.CreatorRevision']"}),
            'death_country_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_death_country_source'", 'null': 'True', 'to': "orm['gcd.DeathCountrySource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathcountrysourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.deathdatesourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathDateSourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deathdatesourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathdatesource'", 'to': "orm['oi.CreatorRevision']"}),
            'death_date_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_death_date_source'", 'null': 'True', 'to': "orm['gcd.DeathDateSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathdatesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.deathmonthsourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathMonthSourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deathmonthsourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathmonthsource'", 'to': "orm['oi.CreatorRevision']"}),
            'death_month_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_death_month_source'", 'null': 'True', 'to': "orm['gcd.DeathMonthSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathmonthsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.deathprovincesourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathProvinceSourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deathprovincesourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathprovincesource'", 'to': "orm['oi.CreatorRevision']"}),
            'death_province_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_death_province_source'", 'null': 'True', 'to': "orm['gcd.DeathProvinceSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathprovincesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.deathyearsourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'DeathYearSourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'deathyearsourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathyearsource'", 'to': "orm['oi.CreatorRevision']"}),
            'death_year_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_death_year_source'", 'null': 'True', 'to': "orm['gcd.DeathYearSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatordeathyearsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.download': {
            'Meta': {'object_name': 'Download'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'oi.imagerevision': {
            'Meta': {'ordering': "['created']", 'object_name': 'ImageRevision', 'db_table': "'oi_image_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imagerevisions'", 'to': "orm['oi.Changeset']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Image']"}),
            'image_file': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'is_replacement': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.ImageType']"})
        },
        'oi.indiciapublisherrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'IndiciaPublisherRevision', 'db_table': "'oi_indicia_publisher_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indiciapublisherrevisions'", 'to': "orm['oi.Changeset']"}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indicia_publishers_revisions'", 'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indicia_publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.IndiciaPublisher']"}),
            'is_surrogate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'indicia_publisher_revisions'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.issuerevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'IssueRevision', 'db_table': "'oi_issue_revision'"},
            'after': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'after_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'barcode': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '38', 'blank': 'True'}),
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'issue_revisions'", 'null': 'True', 'blank': 'True', 'to': "orm['gcd.Brand']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'issuerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'day_on_sale': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'display_volume_with_number': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'editing': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indicia_frequency': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'indicia_pub_not_printed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'indicia_publisher': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'issue_revisions'", 'null': 'True', 'blank': 'True', 'to': "orm['gcd.IndiciaPublisher']"}),
            'isbn': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '32', 'blank': 'True'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'key_date': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '10', 'blank': 'True'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'month_on_sale': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'no_barcode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_brand': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_editing': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_indicia_frequency': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_isbn': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_rating': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_title': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_volume': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'notes': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'on_sale_date_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'page_count': ('django.db.models.fields.DecimalField', [], {'default': 'None', 'null': 'True', 'max_digits': '10', 'decimal_places': '3', 'blank': 'True'}),
            'page_count_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'price': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'publication_date': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'rating': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'reservation_requested': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'revision_sort_code': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'series': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'issue_revisions'", 'to': "orm['gcd.Series']"}),
            'title': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'variant_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'variant_of': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'variant_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'volume': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '50', 'blank': 'True'}),
            'year_on_sale': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'})
        },
        'oi.namerelationrevision': {
            'Meta': {'ordering': "('gcd_official_name', 'rel_type', 'to_name')", 'object_name': 'NameRelationRevision', 'db_table': "'oi_namerelation_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'namerelationrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'gcd_official_name': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creator_revise_gcd_official_name'", 'to': "orm['oi.CreatorRevision']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name_relation': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_name_relation'", 'null': 'True', 'to': "orm['gcd.NameRelation']"}),
            'rel_source': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'rel_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creator_revise_relation_type'", 'to': "orm['oi.RelationTypeRevision']"}),
            'to_name': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creator_revise_to_name'", 'to': "orm['oi.CreatorRevision']"})
        },
        'oi.namesourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'NameSourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'namesourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatornamesource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_name_source'", 'null': 'True', 'to': "orm['gcd.NameSource']"}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_namesourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.ongoingreservation': {
            'Meta': {'object_name': 'OngoingReservation', 'db_table': "'oi_ongoing_reservation'"},
            'along_with': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'ongoing_assisting'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ongoing_reservations'", 'to': "orm['auth.User']"}),
            'on_behalf_of': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'ongoing_source'", 'symmetrical': 'False', 'to': "orm['auth.User']"}),
            'series': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'ongoing_reservation'", 'unique': 'True', 'to': "orm['gcd.Series']"})
        },
        'oi.portraitsourcerevision': {
            'Meta': {'ordering': "('source_description',)", 'object_name': 'PortraitSourceRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'portraitsourcerevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorportraitsource'", 'to': "orm['oi.CreatorRevision']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'portrait_source': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_portrait_source'", 'null': 'True', 'to': "orm['gcd.PortraitSource']"}),
            'source_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'source_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_creatorportraitsourcetype'", 'to': "orm['gcd.SourceType']"})
        },
        'oi.publisherrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'PublisherRevision', 'db_table': "'oi_publisher_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'publisherrevisions'", 'to': "orm['oi.Changeset']"}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_master': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'imprint_revisions'", 'null': 'True', 'blank': 'True', 'to': "orm['gcd.Publisher']"}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.relationtyperevision': {
            'Meta': {'ordering': "('type',)", 'object_name': 'RelationTypeRevision'},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'relationtyperevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'relation_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cr_relation_type'", 'null': 'True', 'to': "orm['gcd.RelationType']"}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'oi.reprintrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'ReprintRevision', 'db_table': "'oi_reprint_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reprintrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'issue_reprint': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.IssueReprint']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'default': "''", 'max_length': '255'}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'origin_revision': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_reprint_revisions'", 'null': 'True', 'to': "orm['oi.StoryRevision']"}),
            'origin_story': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Story']"}),
            'out_type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'previous_revision': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'next_revision'", 'unique': 'True', 'null': 'True', 'to': "orm['oi.ReprintRevision']"}),
            'reprint': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Reprint']"}),
            'reprint_from_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.ReprintFromIssue']"}),
            'reprint_to_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.ReprintToIssue']"}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'target_revision': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_reprint_revisions'", 'null': 'True', 'to': "orm['oi.StoryRevision']"}),
            'target_story': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Story']"})
        },
        'oi.seriesbondrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'SeriesBondRevision', 'db_table': "'oi_series_bond_revision'"},
            'bond_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'bond_revisions'", 'null': 'True', 'to': "orm['gcd.SeriesBondType']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'seriesbondrevisions'", 'to': "orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Series']"}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_series_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'previous_revision': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'next_revision'", 'unique': 'True', 'null': 'True', 'to': "orm['oi.SeriesBondRevision']"}),
            'series_bond': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.SeriesBond']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Series']"}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_series_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"})
        },
        'oi.seriesrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'SeriesRevision', 'db_table': "'oi_series_revision'"},
            'binding': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'seriesrevisions'", 'to': "orm['oi.Changeset']"}),
            'color': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'series_revisions'", 'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'dimensions': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'format': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'has_barcode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_indicia_frequency': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_isbn': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_issue_title': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_rating': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_volume': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imprint': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'imprint_series_revisions'", 'null': 'True', 'blank': 'True', 'to': "orm['gcd.Publisher']"}),
            'is_comics_publication': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_current': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_singleton': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'series_revisions'", 'to': "orm['gcd.Language']"}),
            'leading_article': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'paper_stock': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'publication_notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'publication_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.SeriesPublicationType']", 'null': 'True', 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'series_revisions'", 'to': "orm['gcd.Publisher']"}),
            'publishing_format': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'reservation_requested': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'series': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Series']"}),
            'tracking_notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'year_began': ('django.db.models.fields.IntegerField', [], {}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'oi.storyrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'StoryRevision', 'db_table': "'oi_story_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'storyrevisions'", 'to': "orm['oi.Changeset']"}),
            'characters': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'colors': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'editing': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'feature': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'genre': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'inks': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'story_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'job_number': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'keywords': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'letters': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'no_colors': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_editing': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_inks': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_letters': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_pencils': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'no_script': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'page_count': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '3', 'blank': 'True'}),
            'page_count_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pencils': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'reprint_notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'script': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'sequence_number': ('django.db.models.fields.IntegerField', [], {}),
            'story': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Story']"}),
            'synopsis': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'title_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.StoryType']"})
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

    complete_apps = ['oi']