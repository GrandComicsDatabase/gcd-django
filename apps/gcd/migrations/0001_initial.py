# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Country'
        db.create_table('gcd_country', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=10)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Country'])

        # Adding model 'Language'
        db.create_table('gcd_language', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=10)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Language'])

        # Adding model 'ImageType'
        db.create_table('gcd_image_type', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=50, db_index=True)),
            ('unique', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('gcd', ['ImageType'])

        # Adding model 'Image'
        db.create_table('gcd_image', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], null=True)),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, db_index=True)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.ImageType'])),
            ('image_file', self.gf('django.db.models.fields.files.ImageField')(max_length=100)),
            ('marked', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, null=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, null=True, blank=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Image'])

        # Adding model 'Publisher'
        db.create_table('gcd_publisher', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('notes', self.gf('django.db.models.fields.TextField')()),
            ('url', self.gf('django.db.models.fields.URLField')(default=u'', max_length=255, blank=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Country'])),
            ('imprint_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('brand_count', self.gf('django.db.models.fields.IntegerField')(default=0, db_index=True)),
            ('indicia_publisher_count', self.gf('django.db.models.fields.IntegerField')(default=0, db_index=True)),
            ('series_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('issue_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('is_master', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(related_name='imprint_set', null=True, to=orm['gcd.Publisher'])),
        ))
        db.send_create_signal('gcd', ['Publisher'])

        # Adding model 'IndiciaPublisher'
        db.create_table('gcd_indicia_publisher', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('notes', self.gf('django.db.models.fields.TextField')()),
            ('url', self.gf('django.db.models.fields.URLField')(default=u'', max_length=255, blank=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Publisher'])),
            ('is_surrogate', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Country'])),
            ('issue_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('gcd', ['IndiciaPublisher'])

        # Adding model 'Brand'
        db.create_table('gcd_brand', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(null=True, db_index=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('notes', self.gf('django.db.models.fields.TextField')()),
            ('url', self.gf('django.db.models.fields.URLField')(default=u'', max_length=255, blank=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Publisher'])),
            ('issue_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('gcd', ['Brand'])

        # Adding model 'Series'
        db.create_table('gcd_series', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('sort_name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('format', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('notes', self.gf('django.db.models.fields.TextField')()),
            ('year_began', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('year_ended', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('year_began_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('year_ended_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_current', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('publication_dates', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('first_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='first_issue_series_set', null=True, to=orm['gcd.Issue'])),
            ('last_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='last_issue_series_set', null=True, to=orm['gcd.Issue'])),
            ('issue_count', self.gf('django.db.models.fields.IntegerField')()),
            ('publication_notes', self.gf('django.db.models.fields.TextField')()),
            ('tracking_notes', self.gf('django.db.models.fields.TextField')()),
            ('has_barcode', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_indicia_frequency', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_isbn', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_issue_title', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_volume', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_comics_publication', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_gallery', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('open_reserve', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Country'])),
            ('language', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Language'])),
            ('publisher', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Publisher'])),
            ('imprint', self.gf('django.db.models.fields.related.ForeignKey')(related_name='imprint_series_set', null=True, to=orm['gcd.Publisher'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Series'])

        # Adding model 'Issue'
        db.create_table('gcd_issue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('number', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('no_title', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('volume', self.gf('django.db.models.fields.CharField')(max_length=50, db_index=True)),
            ('no_volume', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('display_volume_with_number', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('isbn', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('no_isbn', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('valid_isbn', self.gf('django.db.models.fields.CharField')(max_length=13, db_index=True)),
            ('variant_of', self.gf('django.db.models.fields.related.ForeignKey')(related_name='variant_set', null=True, to=orm['gcd.Issue'])),
            ('variant_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('barcode', self.gf('django.db.models.fields.CharField')(max_length=38, db_index=True)),
            ('no_barcode', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('publication_date', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('key_date', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('on_sale_date', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('on_sale_date_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('sort_code', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('indicia_frequency', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('no_indicia_frequency', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('price', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('page_count', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=3)),
            ('page_count_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('editing', self.gf('django.db.models.fields.TextField')()),
            ('no_editing', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('notes', self.gf('django.db.models.fields.TextField')()),
            ('series', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Series'])),
            ('indicia_publisher', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.IndiciaPublisher'], null=True)),
            ('indicia_pub_not_printed', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('brand', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Brand'], null=True)),
            ('no_brand', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('is_indexed', self.gf('django.db.models.fields.IntegerField')(default=0, db_index=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Issue'])

        # Adding unique constraint on 'Issue', fields ['series', 'sort_code']
        db.create_unique('gcd_issue', ['series_id', 'sort_code'])

        # Adding model 'StoryType'
        db.create_table('gcd_story_type', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=50, db_index=True)),
            ('sort_code', self.gf('django.db.models.fields.IntegerField')(unique=True)),
        ))
        db.send_create_signal('gcd', ['StoryType'])

        # Adding model 'Story'
        db.create_table('gcd_story', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('title_inferred', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('feature', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.StoryType'])),
            ('sequence_number', self.gf('django.db.models.fields.IntegerField')()),
            ('page_count', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=3, db_index=True)),
            ('page_count_uncertain', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('script', self.gf('django.db.models.fields.TextField')()),
            ('pencils', self.gf('django.db.models.fields.TextField')()),
            ('inks', self.gf('django.db.models.fields.TextField')()),
            ('colors', self.gf('django.db.models.fields.TextField')()),
            ('letters', self.gf('django.db.models.fields.TextField')()),
            ('editing', self.gf('django.db.models.fields.TextField')()),
            ('no_script', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('no_pencils', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('no_inks', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('no_colors', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('no_letters', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('no_editing', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('job_number', self.gf('django.db.models.fields.CharField')(max_length=25)),
            ('genre', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('characters', self.gf('django.db.models.fields.TextField')()),
            ('synopsis', self.gf('django.db.models.fields.TextField')()),
            ('reprint_notes', self.gf('django.db.models.fields.TextField')()),
            ('notes', self.gf('django.db.models.fields.TextField')()),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Issue'])),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Story'])

        # Adding model 'Cover'
        db.create_table('gcd_cover', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Issue'])),
            ('marked', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('limit_display', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_wraparound', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('front_left', self.gf('django.db.models.fields.IntegerField')(default=0, null=True, blank=True)),
            ('front_right', self.gf('django.db.models.fields.IntegerField')(default=0, null=True, blank=True)),
            ('front_bottom', self.gf('django.db.models.fields.IntegerField')(default=0, null=True, blank=True)),
            ('front_top', self.gf('django.db.models.fields.IntegerField')(default=0, null=True, blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, db_index=True, blank=True)),
            ('last_upload', self.gf('django.db.models.fields.DateTimeField')(null=True, db_index=True)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Cover'])

        # Adding model 'Indexer'
        db.create_table('gcd_indexer', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auth.User'], unique=True)),
            ('country', self.gf('django.db.models.fields.related.ForeignKey')(related_name='indexers', to=orm['gcd.Country'])),
            ('interests', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('max_reservations', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('max_ongoing', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('mentor', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='mentees', null=True, to=orm['auth.User'])),
            ('is_new', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('is_banned', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('deceased', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('registration_key', self.gf('django.db.models.fields.CharField')(max_length=40, null=True, db_index=True)),
            ('registration_expires', self.gf('django.db.models.fields.DateField')(db_index=True, null=True, blank=True)),
            ('imps', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('notify_on_approve', self.gf('django.db.models.fields.BooleanField')(default=True, db_index=True)),
            ('collapse_compare_view', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('show_wiki_links', self.gf('django.db.models.fields.BooleanField')(default=True, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Indexer'])

        # Adding M2M table for field languages on 'Indexer'
        db.create_table('gcd_indexer_languages', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('indexer', models.ForeignKey(orm['gcd.indexer'], null=False)),
            ('language', models.ForeignKey(orm['gcd.language'], null=False))
        ))
        db.create_unique('gcd_indexer_languages', ['indexer_id', 'language_id'])

        # Adding model 'ImpGrant'
        db.create_table('gcd_imp_grant', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('indexer', self.gf('django.db.models.fields.related.ForeignKey')(related_name='imp_grant_set', to=orm['gcd.Indexer'])),
            ('imps', self.gf('django.db.models.fields.IntegerField')()),
            ('grant_type', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('notes', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('gcd', ['ImpGrant'])

        # Adding model 'IndexCredit'
        db.create_table('gcd_series_indexers', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('indexer', self.gf('django.db.models.fields.related.ForeignKey')(related_name='index_credit_set', to=orm['gcd.Indexer'])),
            ('series', self.gf('django.db.models.fields.related.ForeignKey')(related_name='index_credit_set', to=orm['gcd.Series'])),
            ('run', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('notes', self.gf('django.db.models.fields.TextField')(null=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('gcd', ['IndexCredit'])

        # Adding model 'Reservation'
        db.create_table('gcd_reservation', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('indexer', self.gf('django.db.models.fields.related.ForeignKey')(related_name='reservation_set', to=orm['gcd.Indexer'])),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='reservation_set', to=orm['gcd.Issue'])),
            ('status', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('expires', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('gcd', ['Reservation'])

        # Adding model 'Error'
        db.create_table('gcd_error', (
            ('error_key', self.gf('django.db.models.fields.CharField')(max_length=40, primary_key=True)),
            ('error_text', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('is_safe', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('gcd', ['Error'])

        # Adding model 'CountStats'
        db.create_table('gcd_count_stats', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=40, db_index=True)),
            ('count', self.gf('django.db.models.fields.IntegerField')()),
            ('language', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Language'], null=True)),
        ))
        db.send_create_signal('gcd', ['CountStats'])

        # Adding model 'MigrationStoryStatus'
        db.create_table('gcd_migration_story_status', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('story', self.gf('django.db.models.fields.related.OneToOneField')(related_name='migration_status', unique=True, to=orm['gcd.Story'])),
            ('reprint_needs_inspection', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('reprint_confirmed', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('reprint_original_notes', self.gf('django.db.models.fields.TextField')(null=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('gcd', ['MigrationStoryStatus'])

        # Adding model 'IssueReprint'
        db.create_table('gcd_issue_reprint', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('origin_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='to_issue_reprints', to=orm['gcd.Issue'])),
            ('target_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='from_issue_reprints', to=orm['gcd.Issue'])),
            ('notes', self.gf('django.db.models.fields.TextField')(max_length=255)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['IssueReprint'])

        # Adding model 'Reprint'
        db.create_table('gcd_reprint', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('origin', self.gf('django.db.models.fields.related.ForeignKey')(related_name='to_reprints', to=orm['gcd.Story'])),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(related_name='from_reprints', to=orm['gcd.Story'])),
            ('notes', self.gf('django.db.models.fields.TextField')(max_length=255)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['Reprint'])

        # Adding model 'ReprintToIssue'
        db.create_table('gcd_reprint_to_issue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('origin', self.gf('django.db.models.fields.related.ForeignKey')(related_name='to_issue_reprints', to=orm['gcd.Story'])),
            ('target_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='from_reprints', to=orm['gcd.Issue'])),
            ('notes', self.gf('django.db.models.fields.TextField')(max_length=255)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['ReprintToIssue'])

        # Adding model 'ReprintFromIssue'
        db.create_table('gcd_reprint_from_issue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('origin_issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='to_reprints', to=orm['gcd.Issue'])),
            ('target', self.gf('django.db.models.fields.related.ForeignKey')(related_name='from_issue_reprints', to=orm['gcd.Story'])),
            ('notes', self.gf('django.db.models.fields.TextField')(max_length=255)),
            ('reserved', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
        ))
        db.send_create_signal('gcd', ['ReprintFromIssue'])

        # Adding model 'RecentIndexedIssue'
        db.create_table('gcd_recent_indexed_issue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Issue'])),
            ('language', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['gcd.Language'], null=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
        ))
        db.send_create_signal('gcd', ['RecentIndexedIssue'])


    def backwards(self, orm):
        # Removing unique constraint on 'Issue', fields ['series', 'sort_code']
        db.delete_unique('gcd_issue', ['series_id', 'sort_code'])

        # Deleting model 'Country'
        db.delete_table('gcd_country')

        # Deleting model 'Language'
        db.delete_table('gcd_language')

        # Deleting model 'ImageType'
        db.delete_table('gcd_image_type')

        # Deleting model 'Image'
        db.delete_table('gcd_image')

        # Deleting model 'Publisher'
        db.delete_table('gcd_publisher')

        # Deleting model 'IndiciaPublisher'
        db.delete_table('gcd_indicia_publisher')

        # Deleting model 'Brand'
        db.delete_table('gcd_brand')

        # Deleting model 'Series'
        db.delete_table('gcd_series')

        # Deleting model 'Issue'
        db.delete_table('gcd_issue')

        # Deleting model 'StoryType'
        db.delete_table('gcd_story_type')

        # Deleting model 'Story'
        db.delete_table('gcd_story')

        # Deleting model 'Cover'
        db.delete_table('gcd_cover')

        # Deleting model 'Indexer'
        db.delete_table('gcd_indexer')

        # Removing M2M table for field languages on 'Indexer'
        db.delete_table('gcd_indexer_languages')

        # Deleting model 'ImpGrant'
        db.delete_table('gcd_imp_grant')

        # Deleting model 'IndexCredit'
        db.delete_table('gcd_series_indexers')

        # Deleting model 'Reservation'
        db.delete_table('gcd_reservation')

        # Deleting model 'Error'
        db.delete_table('gcd_error')

        # Deleting model 'CountStats'
        db.delete_table('gcd_count_stats')

        # Deleting model 'MigrationStoryStatus'
        db.delete_table('gcd_migration_story_status')

        # Deleting model 'IssueReprint'
        db.delete_table('gcd_issue_reprint')

        # Deleting model 'Reprint'
        db.delete_table('gcd_reprint')

        # Deleting model 'ReprintToIssue'
        db.delete_table('gcd_reprint_to_issue')

        # Deleting model 'ReprintFromIssue'
        db.delete_table('gcd_reprint_from_issue')

        # Deleting model 'RecentIndexedIssue'
        db.delete_table('gcd_recent_indexed_issue')


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
        'gcd.brand': {
            'Meta': {'ordering': "['name']", 'object_name': 'Brand'},
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
        'gcd.country': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Country'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '10'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'gcd.countstats': {
            'Meta': {'object_name': 'CountStats', 'db_table': "'gcd_count_stats'"},
            'count': ('django.db.models.fields.IntegerField', [], {}),
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
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imps': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'interests': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'is_banned': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'is_new': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'languages': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'indexers'", 'symmetrical': 'False', 'db_table': "'gcd_indexer_languages'", 'to': "orm['gcd.Language']"}),
            'max_ongoing': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'max_reservations': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'mentor': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'mentees'", 'null': 'True', 'to': "orm['auth.User']"}),
            'notify_on_approve': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
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
        'gcd.migrationstorystatus': {
            'Meta': {'object_name': 'MigrationStoryStatus', 'db_table': "'gcd_migration_story_status'"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'reprint_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'reprint_needs_inspection': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'reprint_original_notes': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'story': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'migration_status'", 'unique': 'True', 'to': "orm['gcd.Story']"})
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
        'gcd.series': {
            'Meta': {'ordering': "['sort_name', 'year_began']", 'object_name': 'Series'},
            'country': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Country']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'first_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'first_issue_series_set'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'format': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'has_barcode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_gallery': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'has_indicia_frequency': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_isbn': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_issue_title': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'has_volume': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imprint': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'imprint_series_set'", 'null': 'True', 'to': "orm['gcd.Publisher']"}),
            'is_comics_publication': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_current': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'issue_count': ('django.db.models.fields.IntegerField', [], {}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Language']"}),
            'last_issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'last_issue_series_set'", 'null': 'True', 'to': "orm['gcd.Issue']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {}),
            'open_reserve': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'publication_dates': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'publication_notes': ('django.db.models.fields.TextField', [], {}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['gcd.Publisher']"}),
            'reserved': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'sort_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'tracking_notes': ('django.db.models.fields.TextField', [], {}),
            'year_began': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'year_began_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'year_ended': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year_ended_uncertain': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
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