# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Changeset'
        db.create_table(u'oi_changeset', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('indexer', self.gf('django.db.models.fields.related.ForeignKey')(related_name='changesets', to=orm['auth.User'])),
            ('approver', self.gf('django.db.models.fields.related.ForeignKey')(related_name='approved_changeset', null=True, to=orm['auth.User'])),
            ('change_type', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('migrated', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('date_inferred', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('imps', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
        ))
        db.send_create_signal(u'oi', ['Changeset'])

        # Adding M2M table for field along_with on 'Changeset'
        m2m_table_name = db.shorten_name(u'oi_changeset_along_with')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('changeset', models.ForeignKey(orm[u'oi.changeset'], null=False)),
            ('user', models.ForeignKey(orm[u'auth.user'], null=False))
        ))
        db.create_unique(m2m_table_name, ['changeset_id', 'user_id'])

        # Adding M2M table for field on_behalf_of on 'Changeset'
        m2m_table_name = db.shorten_name(u'oi_changeset_on_behalf_of')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('changeset', models.ForeignKey(orm[u'oi.changeset'], null=False)),
            ('user', models.ForeignKey(orm[u'auth.user'], null=False))
        ))
        db.create_unique(m2m_table_name, ['changeset_id', 'user_id'])

        # Adding model 'ChangesetComment'
        db.create_table('oi_changeset_comment', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('commenter', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('text', self.gf('django.db.models.fields.TextField')()),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='comments', to=orm['oi.Changeset'])),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], null=True)),
            ('revision_id', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('old_state', self.gf('django.db.models.fields.IntegerField')()),
            ('new_state', self.gf('django.db.models.fields.IntegerField')()),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'oi', ['ChangesetComment'])

        # Adding model 'RevisionLock'
        db.create_table('oi_revision_lock', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revision_locks', null=True, to=orm['oi.Changeset'])),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
        ))
        db.send_create_signal(u'oi', ['RevisionLock'])

        # Adding unique constraint on 'RevisionLock', fields ['content_type', 'object_id']
        db.create_unique('oi_revision_lock', ['content_type_id', 'object_id'])

        # Adding model 'OngoingReservation'
        db.create_table('oi_ongoing_reservation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('indexer', self.gf('django.db.models.fields.related.ForeignKey')(related_name='ongoing_reservations', to=orm['auth.User'])),
            ('series', self.gf('django.db.models.fields.related.OneToOneField')(related_name='ongoing_reservation', unique=True, to=orm['gcd.Series'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
        ))
        db.send_create_signal(u'oi', ['OngoingReservation'])

        # Adding M2M table for field along_with on 'OngoingReservation'
        m2m_table_name = db.shorten_name('oi_ongoing_reservation_along_with')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('ongoingreservation', models.ForeignKey(orm[u'oi.ongoingreservation'], null=False)),
            ('user', models.ForeignKey(orm[u'auth.user'], null=False))
        ))
        db.create_unique(m2m_table_name, ['ongoingreservation_id', 'user_id'])

        # Adding M2M table for field on_behalf_of on 'OngoingReservation'
        m2m_table_name = db.shorten_name('oi_ongoing_reservation_on_behalf_of')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('ongoingreservation', models.ForeignKey(orm[u'oi.ongoingreservation'], null=False)),
            ('user', models.ForeignKey(orm[u'auth.user'], null=False))
        ))
        db.create_unique(m2m_table_name, ['ongoingreservation_id', 'user_id'])

        # Adding model 'PublisherRevision'
        db.create_table('oi_publisher_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='publisherrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('publisher', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Publisher'])),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Country'])),
            ('is_master', self.gf('django.db.models.fields.BooleanField')(default=True, db_index=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='imprint_revisions', null=True, blank=True, to=orm['gcd.Publisher'])),
            ('date_inferred', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'oi', ['PublisherRevision'])

        # Adding model 'IndiciaPublisherRevision'
        db.create_table('oi_indicia_publisher_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='indiciapublisherrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('indicia_publisher', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.IndiciaPublisher'])),
            ('is_surrogate', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(related_name='indicia_publishers_revisions', to=orm['gcd.Country'])),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='indicia_publisher_revisions', null=True, to=orm['gcd.Publisher'])),
        ))
        db.send_create_signal(u'oi', ['IndiciaPublisherRevision'])

        # Adding model 'BrandGroupRevision'
        db.create_table('oi_brand_group_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='brandgrouprevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('brand_group', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.BrandGroup'])),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='brand_group_revisions', null=True, to=orm['gcd.Publisher'])),
        ))
        db.send_create_signal(u'oi', ['BrandGroupRevision'])

        # Adding model 'BrandRevision'
        db.create_table('oi_brand_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='brandrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Brand'])),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='brand_revisions', null=True, to=orm['gcd.Publisher'])),
        ))
        db.send_create_signal(u'oi', ['BrandRevision'])

        # Adding M2M table for field group on 'BrandRevision'
        m2m_table_name = db.shorten_name('oi_brand_revision_group')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('brandrevision', models.ForeignKey(orm[u'oi.brandrevision'], null=False)),
            ('brandgroup', models.ForeignKey(orm['gcd.brandgroup'], null=False))
        ))
        db.create_unique(m2m_table_name, ['brandrevision_id', 'brandgroup_id'])

        # Adding model 'BrandUseRevision'
        db.create_table('oi_brand_use_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='branduserevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('brand_use', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.BrandUse'])),
            ('emblem', self.gf('django.db.models.fields.related.ForeignKey')(related_name='use_revisions', null=True, to=orm['gcd.Brand'])),
            ('publisher', self.gf('django.db.models.fields.related.ForeignKey')(related_name='brand_use_revisions', null=True, to=orm['gcd.Publisher'])),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(max_length=255, blank=True)),
        ))
        db.send_create_signal(u'oi', ['BrandUseRevision'])

        # Adding model 'CoverRevision'
        db.create_table('oi_cover_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='coverrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('cover', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Cover'])),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='cover_revisions', to=orm['gcd.Issue'])),
            ('marked', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_replacement', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_wraparound', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('front_left', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
            ('front_right', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
            ('front_bottom', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
            ('front_top', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
            ('file_source', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
        ))
        db.send_create_signal(u'oi', ['CoverRevision'])

        # Adding model 'SeriesRevision'
        db.create_table('oi_series_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='seriesrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('series', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Series'])),
            ('reservation_requested', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('leading_article', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('format', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('color', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('dimensions', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('paper_stock', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('binding', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('publishing_format', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('publication_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.SeriesPublicationType'], null=True, blank=True)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')()),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_current', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('publication_notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('tracking_notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('has_barcode', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_indicia_frequency', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_isbn', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_issue_title', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_volume', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_rating', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_comics_publication', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_singleton', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(related_name='series_revisions', to=orm['gcd.Country'])),
            ('language', self.gf('django.db.models.fields.related.ForeignKey')(related_name='series_revisions', to=orm['gcd.Language'])),
            ('publisher', self.gf('django.db.models.fields.related.ForeignKey')(related_name='series_revisions', to=orm['gcd.Publisher'])),
            ('imprint', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='imprint_series_revisions', null=True, blank=True, to=orm['gcd.Publisher'])),
            ('date_inferred', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'oi', ['SeriesRevision'])

        # Adding model 'SeriesBondRevision'
        db.create_table('oi_series_bond_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='seriesbondrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('series_bond', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.SeriesBond'])),
            ('origin', self.gf('django.db.models.fields.related.ForeignKey')(related_name='origin_bond_revisions', null=True, to=orm['gcd.Series'])),
            ('origin_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='origin_series_bond_revisions', null=True, to=orm['gcd.Issue'])),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(related_name='target_bond_revisions', null=True, to=orm['gcd.Series'])),
            ('target_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='target_series_bond_revisions', null=True, to=orm['gcd.Issue'])),
            ('bond_type', self.gf('django.db.models.fields.related.ForeignKey')(related_name='bond_revisions', null=True, to=orm['gcd.SeriesBondType'])),
            ('notes', self.gf('django.db.models.fields.TextField')(default='', max_length=255, blank=True)),
            ('previous_revision', self.gf('django.db.models.fields.related.OneToOneField')(related_name='next_revision', unique=True, null=True, to=orm['oi.SeriesBondRevision'])),
        ))
        db.send_create_signal(u'oi', ['SeriesBondRevision'])

        # Adding model 'IssueRevision'
        db.create_table('oi_issue_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='issuerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Issue'])),
            ('after', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='after_revisions', null=True, to=orm['gcd.Issue'])),
            ('revision_sort_code', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('reservation_requested', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('number', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('title', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('no_title', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('volume', self.gf('django.db.models.fields.CharField')(default='', max_length=50, blank=True)),
            ('no_volume', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('display_volume_with_number', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('variant_of', self.gf('django.db.models.fields.related.ForeignKey')(related_name='variant_revisions', null=True, to=orm['gcd.Issue'])),
            ('variant_name', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('publication_date', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('key_date', self.gf('django.db.models.fields.CharField')(default='', max_length=10, blank=True)),
            ('year_on_sale', self.gf('django.db.models.fields.IntegerField')(db_index=True, null=True, blank=True)),
            ('month_on_sale', self.gf('django.db.models.fields.IntegerField')(db_index=True, null=True, blank=True)),
            ('day_on_sale', self.gf('django.db.models.fields.IntegerField')(db_index=True, null=True, blank=True)),
            ('on_sale_date_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('indicia_frequency', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('no_indicia_frequency', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('price', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('page_count', self.gf('django.db.models.fields.DecimalField')(default=None, null=True, max_digits=10, decimal_places=3, blank=True)),
            ('page_count_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('editing', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('no_editing', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('notes', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('series', self.gf('django.db.models.fields.related.ForeignKey')(related_name='issue_revisions', to=orm['gcd.Series'])),
            ('indicia_publisher', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='issue_revisions', null=True, blank=True, to=orm['gcd.IndiciaPublisher'])),
            ('indicia_pub_not_printed', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='issue_revisions', null=True, blank=True, to=orm['gcd.Brand'])),
            ('no_brand', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('isbn', self.gf('django.db.models.fields.CharField')(default='', max_length=32, blank=True)),
            ('no_isbn', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('barcode', self.gf('django.db.models.fields.CharField')(default='', max_length=38, blank=True)),
            ('no_barcode', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('rating', self.gf('django.db.models.fields.CharField')(default='', max_length=255, blank=True)),
            ('no_rating', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('date_inferred', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'oi', ['IssueRevision'])

        # Adding model 'StoryRevision'
        db.create_table('oi_story_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='storyrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('story', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Story'])),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('title_inferred', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('feature', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.StoryType'])),
            ('sequence_number', self.gf('django.db.models.fields.IntegerField')()),
            ('page_count', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=3, blank=True)),
            ('page_count_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('script', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('pencils', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('inks', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('colors', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('letters', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('editing', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('no_script', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('no_pencils', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('no_inks', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('no_colors', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('no_letters', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('no_editing', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('job_number', self.gf('django.db.models.fields.CharField')(max_length=25, blank=True)),
            ('genre', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('characters', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('synopsis', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('reprint_notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('notes', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('keywords', self.gf('django.db.models.fields.TextField')(default='', blank=True)),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='story_revisions', null=True, to=orm['gcd.Issue'])),
            ('date_inferred', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'oi', ['StoryRevision'])

        # Adding model 'ReprintRevision'
        db.create_table('oi_reprint_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='reprintrevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('reprint', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Reprint'])),
            ('reprint_from_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.ReprintFromIssue'])),
            ('reprint_to_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.ReprintToIssue'])),
            ('issue_reprint', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.IssueReprint'])),
            ('origin_story', self.gf('django.db.models.fields.related.ForeignKey')(related_name='origin_reprint_revisions', null=True, to=orm['gcd.Story'])),
            ('origin_revision', self.gf('django.db.models.fields.related.ForeignKey')(related_name='origin_reprint_revisions', null=True, to=orm['oi.StoryRevision'])),
            ('origin_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='origin_reprint_revisions', null=True, to=orm['gcd.Issue'])),
            ('target_story', self.gf('django.db.models.fields.related.ForeignKey')(related_name='target_reprint_revisions', null=True, to=orm['gcd.Story'])),
            ('target_revision', self.gf('django.db.models.fields.related.ForeignKey')(related_name='target_reprint_revisions', null=True, to=orm['oi.StoryRevision'])),
            ('target_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='target_reprint_revisions', null=True, to=orm['gcd.Issue'])),
            ('notes', self.gf('django.db.models.fields.TextField')(default='', max_length=255)),
            ('in_type', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('out_type', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('previous_revision', self.gf('django.db.models.fields.related.OneToOneField')(related_name='next_revision', unique=True, null=True, to=orm['oi.ReprintRevision'])),
        ))
        db.send_create_signal(u'oi', ['ReprintRevision'])

        # Adding model 'Download'
        db.create_table(u'oi_download', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('description', self.gf('django.db.models.fields.TextField')()),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'oi', ['Download'])

        # Adding model 'ImageRevision'
        db.create_table('oi_image_revision', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('changeset', self.gf('django.db.models.fields.related.ForeignKey')(related_name='imagerevisions', to=orm['oi.Changeset'])),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('image', self.gf('django.db.models.fields.related.ForeignKey')(related_name='revisions', null=True, to=orm['gcd.Image'])),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], null=True)),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.ImageType'])),
            ('image_file', self.gf('django.db.models.fields.files.ImageField')(max_length=100)),
            ('marked', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_replacement', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'oi', ['ImageRevision'])


    def backwards(self, orm):
        # Removing unique constraint on 'RevisionLock', fields ['content_type', 'object_id']
        db.delete_unique('oi_revision_lock', ['content_type_id', 'object_id'])

        # Deleting model 'Changeset'
        db.delete_table(u'oi_changeset')

        # Removing M2M table for field along_with on 'Changeset'
        db.delete_table(db.shorten_name(u'oi_changeset_along_with'))

        # Removing M2M table for field on_behalf_of on 'Changeset'
        db.delete_table(db.shorten_name(u'oi_changeset_on_behalf_of'))

        # Deleting model 'ChangesetComment'
        db.delete_table('oi_changeset_comment')

        # Deleting model 'RevisionLock'
        db.delete_table('oi_revision_lock')

        # Deleting model 'OngoingReservation'
        db.delete_table('oi_ongoing_reservation')

        # Removing M2M table for field along_with on 'OngoingReservation'
        db.delete_table(db.shorten_name('oi_ongoing_reservation_along_with'))

        # Removing M2M table for field on_behalf_of on 'OngoingReservation'
        db.delete_table(db.shorten_name('oi_ongoing_reservation_on_behalf_of'))

        # Deleting model 'PublisherRevision'
        db.delete_table('oi_publisher_revision')

        # Deleting model 'IndiciaPublisherRevision'
        db.delete_table('oi_indicia_publisher_revision')

        # Deleting model 'BrandGroupRevision'
        db.delete_table('oi_brand_group_revision')

        # Deleting model 'BrandRevision'
        db.delete_table('oi_brand_revision')

        # Removing M2M table for field group on 'BrandRevision'
        db.delete_table(db.shorten_name('oi_brand_revision_group'))

        # Deleting model 'BrandUseRevision'
        db.delete_table('oi_brand_use_revision')

        # Deleting model 'CoverRevision'
        db.delete_table('oi_cover_revision')

        # Deleting model 'SeriesRevision'
        db.delete_table('oi_series_revision')

        # Deleting model 'SeriesBondRevision'
        db.delete_table('oi_series_bond_revision')

        # Deleting model 'IssueRevision'
        db.delete_table('oi_issue_revision')

        # Deleting model 'StoryRevision'
        db.delete_table('oi_story_revision')

        # Deleting model 'ReprintRevision'
        db.delete_table('oi_reprint_revision')

        # Deleting model 'Download'
        db.delete_table(u'oi_download')

        # Deleting model 'ImageRevision'
        db.delete_table('oi_image_revision')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'gcd.brand': {
            'Meta': {'ordering': "['name']", 'object_name': 'Brand'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'group': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['gcd.BrandGroup']", 'symmetrical': 'False', 'db_table': "'gcd_brand_emblem_group'", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_wraparound': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Issue']"}),
            'last_upload': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'limit_display': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'})
        },
        'gcd.image': {
            'Meta': {'object_name': 'Image'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'}),
            'unique': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'gcd.indiciapublisher': {
            'Meta': {'ordering': "['name']", 'object_name': 'IndiciaPublisher', 'db_table': "'gcd_indicia_publisher'"},
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_issue_reprints'", 'to': "orm['gcd.Issue']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_issue_reprints'", 'to': "orm['gcd.Issue']"})
        },
        'gcd.language': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '10'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'gcd.publisher': {
            'Meta': {'ordering': "['name']", 'object_name': 'Publisher'},
            'brand_count': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        'gcd.reprint': {
            'Meta': {'object_name': 'Reprint'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_reprints'", 'to': "orm['gcd.Story']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_reprints'", 'to': "orm['gcd.Story']"})
        },
        'gcd.reprintfromissue': {
            'Meta': {'object_name': 'ReprintFromIssue', 'db_table': "'gcd_reprint_from_issue'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_reprints'", 'to': "orm['gcd.Issue']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_issue_reprints'", 'to': "orm['gcd.Story']"})
        },
        'gcd.reprinttoissue': {
            'Meta': {'object_name': 'ReprintToIssue', 'db_table': "'gcd_reprint_to_issue'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'to_issue_reprints'", 'to': "orm['gcd.Story']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'from_reprints'", 'to': "orm['gcd.Issue']"})
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'gcd.seriespublicationtype': {
            'Meta': {'ordering': "['name']", 'object_name': 'SeriesPublicationType', 'db_table': "'gcd_series_publication_type'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {})
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'}),
            'sort_code': ('django.db.models.fields.IntegerField', [], {'unique': 'True'})
        },
        u'oi.brandgrouprevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'BrandGroupRevision', 'db_table': "'oi_brand_group_revision'"},
            'brand_group': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.BrandGroup']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'brandgrouprevisions'", 'to': u"orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        u'oi.brandrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'BrandRevision', 'db_table': "'oi_brand_revision'"},
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Brand']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'brandrevisions'", 'to': u"orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'group': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'brand_revisions'", 'symmetrical': 'False', 'to': "orm['gcd.BrandGroup']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        u'oi.branduserevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'BrandUseRevision', 'db_table': "'oi_brand_use_revision'"},
            'brand_use': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.BrandUse']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'branduserevisions'", 'to': u"orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'emblem': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'use_revisions'", 'null': 'True', 'to': "orm['gcd.Brand']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'max_length': '255', 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'brand_use_revisions'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'oi.changeset': {
            'Meta': {'object_name': 'Changeset'},
            'along_with': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'changesets_assisting'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'approver': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'approved_changeset'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'change_type': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imps': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'changesets'", 'to': u"orm['auth.User']"}),
            'migrated': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'on_behalf_of': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'changesets_source'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'state': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        },
        u'oi.changesetcomment': {
            'Meta': {'ordering': "['created']", 'object_name': 'ChangesetComment', 'db_table': "'oi_changeset_comment'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': u"orm['oi.Changeset']"}),
            'commenter': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'new_state': ('django.db.models.fields.IntegerField', [], {}),
            'old_state': ('django.db.models.fields.IntegerField', [], {}),
            'revision_id': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {})
        },
        u'oi.coverrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'CoverRevision', 'db_table': "'oi_cover_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'coverrevisions'", 'to': u"orm['oi.Changeset']"}),
            'cover': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Cover']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'file_source': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'front_bottom': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'front_left': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'front_right': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'front_top': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_replacement': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_wraparound': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'cover_revisions'", 'to': "orm['gcd.Issue']"}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'})
        },
        u'oi.download': {
            'Meta': {'object_name': 'Download'},
            'description': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'oi.imagerevision': {
            'Meta': {'ordering': "['created']", 'object_name': 'ImageRevision', 'db_table': "'oi_image_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imagerevisions'", 'to': u"orm['oi.Changeset']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Image']"}),
            'image_file': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'is_replacement': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'marked': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.ImageType']"})
        },
        u'oi.indiciapublisherrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'IndiciaPublisherRevision', 'db_table': "'oi_indicia_publisher_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indiciapublisherrevisions'", 'to': u"orm['oi.Changeset']"}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'indicia_publishers_revisions'", 'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        u'oi.issuerevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'IssueRevision', 'db_table': "'oi_issue_revision'"},
            'after': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'after_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'barcode': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '38', 'blank': 'True'}),
            'brand': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'issue_revisions'", 'null': 'True', 'blank': 'True', 'to': "orm['gcd.Brand']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'issuerevisions'", 'to': u"orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'day_on_sale': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'display_volume_with_number': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'editing': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        u'oi.ongoingreservation': {
            'Meta': {'object_name': 'OngoingReservation', 'db_table': "'oi_ongoing_reservation'"},
            'along_with': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'ongoing_assisting'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'indexer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ongoing_reservations'", 'to': u"orm['auth.User']"}),
            'on_behalf_of': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'ongoing_source'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'series': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'ongoing_reservation'", 'unique': 'True', 'to': "orm['gcd.Series']"})
        },
        u'oi.publisherrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'PublisherRevision', 'db_table': "'oi_publisher_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'publisherrevisions'", 'to': u"orm['oi.Changeset']"}),
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        u'oi.reprintrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'ReprintRevision', 'db_table': "'oi_reprint_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reprintrevisions'", 'to': u"orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'issue_reprint': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.IssueReprint']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'default': "''", 'max_length': '255'}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'origin_revision': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_reprint_revisions'", 'null': 'True', 'to': u"orm['oi.StoryRevision']"}),
            'origin_story': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Story']"}),
            'out_type': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'previous_revision': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'next_revision'", 'unique': 'True', 'null': 'True', 'to': u"orm['oi.ReprintRevision']"}),
            'reprint': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.Reprint']"}),
            'reprint_from_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.ReprintFromIssue']"}),
            'reprint_to_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.ReprintToIssue']"}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'target_revision': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_reprint_revisions'", 'null': 'True', 'to': u"orm['oi.StoryRevision']"}),
            'target_story': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_reprint_revisions'", 'null': 'True', 'to': "orm['gcd.Story']"})
        },
        u'oi.revisionlock': {
            'Meta': {'unique_together': "(('content_type', 'object_id'),)", 'object_name': 'RevisionLock', 'db_table': "'oi_revision_lock'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revision_locks'", 'null': 'True', 'to': u"orm['oi.Changeset']"}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        },
        u'oi.seriesbondrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'SeriesBondRevision', 'db_table': "'oi_series_bond_revision'"},
            'bond_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'bond_revisions'", 'null': 'True', 'to': "orm['gcd.SeriesBondType']"}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'seriesbondrevisions'", 'to': u"orm['oi.Changeset']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'origin': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Series']"}),
            'origin_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'origin_series_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'previous_revision': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'next_revision'", 'unique': 'True', 'null': 'True', 'to': u"orm['oi.SeriesBondRevision']"}),
            'series_bond': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'revisions'", 'null': 'True', 'to': "orm['gcd.SeriesBond']"}),
            'target': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Series']"}),
            'target_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'target_series_bond_revisions'", 'null': 'True', 'to': "orm['gcd.Issue']"})
        },
        u'oi.seriesrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'SeriesRevision', 'db_table': "'oi_series_revision'"},
            'binding': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'seriesrevisions'", 'to': u"orm['oi.Changeset']"}),
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
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        u'oi.storyrevision': {
            'Meta': {'ordering': "['-created', '-id']", 'object_name': 'StoryRevision', 'db_table': "'oi_story_revision'"},
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'storyrevisions'", 'to': u"orm['oi.Changeset']"}),
            'characters': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'colors': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'date_inferred': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'editing': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'feature': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'genre': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
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
        }
    }

    complete_apps = ['oi']