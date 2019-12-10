# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0006_award_editable'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='creatorrelationrevision',
            options={'ordering': ('to_creator', 'relation_type', 'from_creator'), 'verbose_name_plural': 'Creator Relation Revisions'},
        ),
        migrations.AddField(
            model_name='awardrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='awardrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.AwardRevision'),
            preserve_default=True,
        ),
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
            model_name='creatorartinfluencerevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorartinfluencerevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorArtInfluenceRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorawardrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorawardrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorAwardRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordegreerevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordegreerevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorDegreeRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatormembershiprevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatormembershiprevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorMembershipRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetailrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetailrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorNameDetailRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornoncomicworkrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornoncomicworkrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorNonComicWorkRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorrelationrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorrelationrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorRelationRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschoolrevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschoolrevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.CreatorSchoolRevision'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='datasourcerevision',
            name='committed',
            field=models.NullBooleanField(default=None, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='datasourcerevision',
            name='previous_revision',
            field=models.OneToOneField(related_name='next_revision', null=True, to='oi.DataSourceRevision'),
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
