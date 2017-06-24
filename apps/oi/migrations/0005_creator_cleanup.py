# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0003_language_native_name'),
        ('oi', '0004_DataSource'),
    ]

    operations = [
        migrations.RenameField(
            model_name='creatormembershiprevision',
            old_name='membership_begin_year',
            new_name='membership_year_began',
        ),
        migrations.RenameField(
            model_name='creatormembershiprevision',
            old_name='membership_begin_year_uncertain',
            new_name='membership_year_began_uncertain',
        ),
        migrations.RenameField(
            model_name='creatormembershiprevision',
            old_name='membership_end_year',
            new_name='membership_year_ended',
        ),
        migrations.RenameField(
            model_name='creatormembershiprevision',
            old_name='membership_end_year_uncertain',
            new_name='membership_year_ended_uncertain',
        ),
        migrations.RemoveField(
            model_name='creatorartinfluencerevision',
            name='is_self_identify',
        ),
        migrations.RemoveField(
            model_name='creatorartinfluencerevision',
            name='self_identify_influences_doc',
        ),
        migrations.RemoveField(
            model_name='creatornoncomicworkrevision',
            name='work_notes',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='birth_date',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='birth_date_uncertain',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='birth_month',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='birth_month_uncertain',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='birth_year',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='birth_year_uncertain',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='death_date',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='death_date_uncertain',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='death_month',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='death_month_uncertain',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='death_year',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='death_year_uncertain',
        ),
        migrations.AddField(
            model_name='creatorartinfluencerevision',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorawardrevision',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatormembershiprevision',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornoncomicworkrevision',
            name='notes',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorrevision',
            name='birth_day',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorrevision',
            name='death_day',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorartinfluencerevision',
            name='creator',
            field=models.ForeignKey(related_name='art_influence_revisions', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorartinfluencerevision',
            name='influence_link',
            field=models.ForeignKey(related_name='influenced_revisions', blank=True, to='gcd.Creator', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorawardrevision',
            name='creator',
            field=models.ForeignKey(related_name='award_revisions', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatordegreedetailrevision',
            name='creator',
            field=models.ForeignKey(related_name='degree_revisions', to='oi.CreatorRevision'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatormembershiprevision',
            name='creator',
            field=models.ForeignKey(related_name='membership_revisions', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatornoncomicworkrevision',
            name='creator',
            field=models.ForeignKey(related_name='non_comic_work_revisions', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorschooldetailrevision',
            name='creator',
            field=models.ForeignKey(related_name='school_revisions', to='oi.CreatorRevision'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorschooldetailrevision',
            name='creator_school_detail',
            field=models.ForeignKey(related_name='revisions', to='gcd.CreatorSchoolDetail', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='namerelationrevision',
            name='gcd_official_name',
            field=models.ForeignKey(related_name='cr_gcd_official_name', to='oi.CreatorNameDetailRevision'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='namerelationrevision',
            name='rel_type',
            field=models.ForeignKey(related_name='cr_relation_type', blank=True, to='gcd.RelationType', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='namerelationrevision',
            name='to_name',
            field=models.ForeignKey(related_name='cr_to_name', to='oi.CreatorNameDetailRevision'),
            preserve_default=True,
        ),
    ]
