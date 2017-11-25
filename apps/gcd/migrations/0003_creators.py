# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0002_initial_data'),
        ('gcd', '0002_initial_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArtInfluence',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('influence_name', models.CharField(max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
            ],
            options={
                'verbose_name_plural': 'Art Influences',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Award',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('award_name', models.CharField(max_length=255)),
                ('no_award_name', models.BooleanField(default=False)),
                ('award_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('award_year_uncertain', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
            ],
            options={
                'ordering': ('award_year',),
                'verbose_name_plural': 'Awards',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AwardType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'AwardTypes',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Creator',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('gcd_official_name', models.CharField(max_length=255, db_index=True)),
                ('whos_who', models.URLField(null=True, blank=True)),
                ('birth_country_uncertain', models.BooleanField(default=False)),
                ('birth_province', models.CharField(max_length=50, blank=True)),
                ('birth_province_uncertain', models.BooleanField(default=False)),
                ('birth_city', models.CharField(max_length=200, blank=True)),
                ('birth_city_uncertain', models.BooleanField(default=False)),
                ('death_country_uncertain', models.BooleanField(default=False)),
                ('death_province', models.CharField(max_length=50, blank=True)),
                ('death_province_uncertain', models.BooleanField(default=False)),
                ('death_city', models.CharField(max_length=200, blank=True)),
                ('death_city_uncertain', models.BooleanField(default=False)),
                ('bio', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('birth_country', models.ForeignKey(related_name='birth_country', blank=True, to='stddata.Country', null=True)),
                ('birth_date', models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True)),
            ],
            options={
                'ordering': ('created',),
                'verbose_name_plural': 'Creators',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CreatorDataSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField()),
                ('field', models.CharField(max_length=256)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Creator Data Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CreatorDegreeDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('degree_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('degree_year_uncertain', models.BooleanField(default=False)),
                ('notes', models.TextField()),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(related_name='creator_degree', to='gcd.Creator')),
                ('data_source', models.ManyToManyField(to='gcd.CreatorDataSource', blank=True)),
            ],
            options={
                'ordering': ('degree_year',),
                'verbose_name_plural': 'Creator Degree Details',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CreatorNameDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(related_name='creator_names', to='gcd.Creator')),
            ],
            options={
                'ordering': ['type__id', 'created', '-id'],
                'verbose_name_plural': 'CreatorName Details',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CreatorSchoolDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('school_year_began', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('school_year_began_uncertain', models.BooleanField(default=False)),
                ('school_year_ended', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('school_year_ended_uncertain', models.BooleanField(default=False)),
                ('notes', models.TextField()),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(related_name='creator_school', to='gcd.Creator')),
                ('data_source', models.ManyToManyField(to='gcd.CreatorDataSource', blank=True)),
            ],
            options={
                'ordering': ('school_year_began', 'school_year_ended'),
                'verbose_name_plural': 'Creator School Details',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Degree',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('degree_name', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ('degree_name',),
                'verbose_name_plural': 'Degrees',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Membership',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('organization_name', models.CharField(max_length=200)),
                ('membership_year_began', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('membership_year_began_uncertain', models.BooleanField(default=False)),
                ('membership_year_ended', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('membership_year_ended_uncertain', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(to='gcd.Creator')),
                ('data_source', models.ManyToManyField(to='gcd.CreatorDataSource', blank=True)),
            ],
            options={
                'ordering': ('membership_type',),
                'verbose_name_plural': 'Memberships',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MembershipType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name_plural': 'Membership Types',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NameRelation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('gcd_official_name', models.ForeignKey(related_name='creator_gcd_official_name', to='gcd.CreatorNameDetail')),
            ],
            options={
                'ordering': ('gcd_official_name', 'rel_type', 'to_name'),
                'verbose_name_plural': 'Name Relations',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NameType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.TextField(null=True)),
                ('type', models.CharField(max_length=50, blank=True)),
            ],
            options={
                'ordering': ('type',),
                'verbose_name_plural': 'Name Types',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NonComicWork',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('publication_title', models.CharField(max_length=200)),
                ('employer_name', models.CharField(max_length=200, blank=True)),
                ('work_title', models.CharField(max_length=255, blank=True)),
                ('work_urls', models.TextField()),
                ('notes', models.TextField()),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(to='gcd.Creator')),
                ('data_source', models.ManyToManyField(to='gcd.CreatorDataSource', blank=True)),
            ],
            options={
                'ordering': ('publication_title', 'employer_name', 'work_type'),
                'verbose_name_plural': 'NonComic Works',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NonComicWorkRole',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('role_name', models.CharField(max_length=200)),
            ],
            options={
                'verbose_name_plural': 'NonComic Work Roles',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NonComicWorkType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name_plural': 'NonComic Work Types',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NonComicWorkYear',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('work_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('work_year_uncertain', models.BooleanField(default=False)),
                ('non_comic_work', models.ForeignKey(related_name='noncomicworkyears', to='gcd.NonComicWork')),
            ],
            options={
                'ordering': ('work_year',),
                'verbose_name_plural': 'NonComic Work Years',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RelationType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=50)),
            ],
            options={
                'ordering': ('type',),
                'verbose_name_plural': 'Relation Types',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='School',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('school_name', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ('school_name',),
                'verbose_name_plural': 'Schools',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SourceType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=50)),
            ],
            options={
                'ordering': ('type',),
                'verbose_name_plural': 'Source Types',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='work_role',
            field=models.ForeignKey(to='gcd.NonComicWorkRole', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='work_type',
            field=models.ForeignKey(to='gcd.NonComicWorkType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='namerelation',
            name='rel_type',
            field=models.ForeignKey(related_name='relation_type', blank=True, to='gcd.RelationType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='namerelation',
            name='to_name',
            field=models.ForeignKey(related_name='to_name', to='gcd.CreatorNameDetail'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='membership',
            name='membership_type',
            field=models.ForeignKey(blank=True, to='gcd.MembershipType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='school',
            field=models.ForeignKey(related_name='school_details', to='gcd.School'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetail',
            name='type',
            field=models.ForeignKey(related_name='nametypes', blank=True, to='gcd.NameType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordegreedetail',
            name='degree',
            field=models.ForeignKey(related_name='degreedetails', to='gcd.Degree'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordegreedetail',
            name='school',
            field=models.ForeignKey(related_name='schooldetails', blank=True, to='gcd.School', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatordatasource',
            name='source_type',
            field=models.ForeignKey(to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_country',
            field=models.ForeignKey(related_name='death_country', blank=True, to='stddata.Country', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_date',
            field=models.ForeignKey(related_name='+', blank=True, to='stddata.Date', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='degrees',
            field=models.ManyToManyField(related_name='degreeinformation', null=True, through='gcd.CreatorDegreeDetail', to='gcd.Degree', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='schools',
            field=models.ManyToManyField(related_name='schoolinformation', null=True, through='gcd.CreatorSchoolDetail', to='gcd.School', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='award',
            field=models.ForeignKey(to='gcd.AwardType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='creator',
            field=models.ForeignKey(to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='artinfluence',
            name='creator',
            field=models.ForeignKey(to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='artinfluence',
            name='data_source',
            field=models.ManyToManyField(to='gcd.CreatorDataSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='artinfluence',
            name='influence_link',
            field=models.ForeignKey(related_name='exist_influencer', blank=True, to='gcd.Creator', null=True),
            preserve_default=True,
        ),
    ]
