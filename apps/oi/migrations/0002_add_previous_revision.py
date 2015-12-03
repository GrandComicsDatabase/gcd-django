# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='brandgrouprevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='brandgrouprevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.BrandGroupRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='brandrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='brandrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.BrandRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='branduserevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='branduserevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.BrandUseRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='coverrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='coverrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CoverRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagerevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagerevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.ImageRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='indiciapublisherrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='indiciapublisherrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.IndiciaPublisherRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='issuerevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='issuerevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.IssueRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='publisherrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='publisherrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.PublisherRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='reprintrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='seriesbondrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='seriesrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='seriesrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.SeriesRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='storyrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='storyrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.StoryRevision'),
            preserve_default=True,
        ),
    ]
