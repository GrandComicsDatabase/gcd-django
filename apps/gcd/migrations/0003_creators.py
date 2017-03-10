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
                ('is_self_identify', models.BooleanField(default=False)),
                ('self_identify_influences_doc', models.TextField(null=True, blank=True)),
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
                ('award_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('award_year_uncertain', models.BooleanField(default=False)),
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
            name='BioSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Bio Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BirthCitySource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Birth City Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BirthCountrySource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Birth Country Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BirthDateSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Birth Date Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BirthMonthSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Birth Month Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BirthProvinceSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Birth Province Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BirthYearSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Birth Year Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Creator',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('gcd_official_name', models.CharField(max_length=255, db_index=True)),
                ('birth_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('birth_year_uncertain', models.BooleanField(default=False)),
                ('birth_month', models.PositiveSmallIntegerField(blank=True, null=True, choices=[(1, b'January'), (2, b'February'), (3, b'March'), (4, b'April'), (5, b'May'), (6, b'June'), (7, b'July'), (8, b'August'), (9, b'September'), (10, b'October'), (11, b'November'), (12, b'December')])),
                ('birth_month_uncertain', models.BooleanField(default=False)),
                ('birth_date', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('birth_date_uncertain', models.BooleanField(default=False)),
                ('death_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('death_year_uncertain', models.BooleanField(default=False)),
                ('death_month', models.PositiveSmallIntegerField(blank=True, null=True, choices=[(1, b'January'), (2, b'February'), (3, b'March'), (4, b'April'), (5, b'May'), (6, b'June'), (7, b'July'), (8, b'August'), (9, b'September'), (10, b'October'), (11, b'November'), (12, b'December')])),
                ('death_month_uncertain', models.BooleanField(default=False)),
                ('death_date', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('death_date_uncertain', models.BooleanField(default=False)),
                ('whos_who', models.URLField(null=True, blank=True)),
                ('birth_country_uncertain', models.BooleanField(default=False)),
                ('birth_province', models.CharField(max_length=50, null=True, blank=True)),
                ('birth_province_uncertain', models.BooleanField(default=False)),
                ('birth_city', models.CharField(max_length=200, null=True, blank=True)),
                ('birth_city_uncertain', models.BooleanField(default=False)),
                ('death_country_uncertain', models.BooleanField(default=False)),
                ('death_province', models.CharField(max_length=50, null=True, blank=True)),
                ('death_province_uncertain', models.BooleanField(default=False)),
                ('death_city', models.CharField(max_length=200, null=True, blank=True)),
                ('death_city_uncertain', models.BooleanField(default=False)),
                ('bio', models.TextField(null=True, blank=True)),
                ('notes', models.TextField(null=True, blank=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
            ],
            options={
                'ordering': ('created',),
                'verbose_name_plural': 'Creators',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CreatorDegreeDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('degree_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('degree_year_uncertain', models.BooleanField(default=False)),
                ('creator', models.ForeignKey(related_name='creator_degree', to='gcd.Creator')),
            ],
            options={
                'ordering': ('degree_year',),
                'verbose_name_plural': 'Creator Degree Details',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CreatorNameDetails',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creator_names', to='gcd.Creator')),
            ],
            options={
                'ordering': ('type',),
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
                ('creator', models.ForeignKey(related_name='creator_school', to='gcd.Creator')),
            ],
            options={
                'ordering': ('school_year_began', 'school_year_ended'),
                'verbose_name_plural': 'Creator School Details',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeathCitySource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatordeathcitysource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Death City Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeathCountrySource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatordeathcountrysource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Death Country Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeathDateSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatordeathdatesource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Death Date Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeathMonthSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatordeathmonthsource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Death Month Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeathProvinceSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatordeathprovincesource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Death Province Source',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeathYearSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatordeathyearsource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Death Year Source',
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
                ('membership_begin_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('membership_begin_year_uncertain', models.BooleanField(default=False)),
                ('membership_end_year', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('membership_end_year_uncertain', models.BooleanField(default=False)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(to='gcd.Creator')),
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
                ('gcd_official_name', models.ForeignKey(related_name='creator_gcd_official_name', to='gcd.CreatorNameDetails')),
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
                ('description', models.TextField(null=True, blank=True)),
                ('type', models.CharField(max_length=50, null=True, blank=True)),
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
                ('employer_name', models.CharField(max_length=200, null=True, blank=True)),
                ('work_title', models.CharField(max_length=255, null=True, blank=True)),
                ('work_notes', models.TextField(null=True, blank=True)),
                ('reserved', models.BooleanField(default=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deleted', models.BooleanField(default=False, db_index=True)),
                ('creator', models.ForeignKey(to='gcd.Creator')),
            ],
            options={
                'ordering': ('publication_title', 'employer_name', 'work_type'),
                'verbose_name_plural': 'NonComic Works',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NonComicWorkLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('link', models.URLField(max_length=255)),
                ('non_comic_work', models.ForeignKey(related_name='noncomicworklinks', to='gcd.NonComicWork')),
            ],
            options={
                'verbose_name_plural': 'NonComic Work Links',
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
            name='PortraitSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('source_description', models.TextField(null=True, blank=True)),
                ('creator', models.ForeignKey(related_name='creatorportraitsource', to='gcd.Creator')),
            ],
            options={
                'ordering': ('source_description',),
                'verbose_name_plural': 'Portrait Source',
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
            model_name='portraitsource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorportraitsourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='work_role',
            field=models.ForeignKey(to='gcd.NonComicWorkRole', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='noncomicwork',
            name='work_source',
            field=models.ManyToManyField(related_name='worksource', null=True, to='gcd.SourceType', blank=True),
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
            name='rel_source',
            field=models.ManyToManyField(to='gcd.SourceType', null=True),
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
            field=models.ForeignKey(related_name='to_name', to='gcd.CreatorNameDetails'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='membership',
            name='membership_source',
            field=models.ManyToManyField(related_name='membershipsource', null=True, to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='membership',
            name='membership_type',
            field=models.ForeignKey(blank=True, to='gcd.MembershipType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deathyearsource',
            name='source_type',
            field=models.ForeignKey(related_name='creatordeathyearsourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deathprovincesource',
            name='source_type',
            field=models.ForeignKey(related_name='creatordeathprovincesourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deathmonthsource',
            name='source_type',
            field=models.ForeignKey(related_name='creatordeathmonthsourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deathdatesource',
            name='source_type',
            field=models.ForeignKey(related_name='creatordeathdatesourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deathcountrysource',
            name='source_type',
            field=models.ForeignKey(related_name='creatordeathcountrysourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deathcitysource',
            name='source_type',
            field=models.ForeignKey(related_name='creatordeathcitysourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='school',
            field=models.ForeignKey(related_name='school_details', to='gcd.School'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatorschooldetail',
            name='school_source',
            field=models.ManyToManyField(related_name='schoolsource', null=True, to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetails',
            name='source',
            field=models.ManyToManyField(related_name='namesources', null=True, to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creatornamedetails',
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
            model_name='creator',
            name='bio_source',
            field=models.ManyToManyField(related_name='biosource', null=True, through='gcd.BioSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_city_source',
            field=models.ManyToManyField(related_name='birthcitysource', null=True, through='gcd.BirthCitySource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_country',
            field=models.ForeignKey(related_name='birth_country', blank=True, to='stddata.Country', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_country_source',
            field=models.ManyToManyField(related_name='birthcountrysource', null=True, through='gcd.BirthCountrySource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_date_source',
            field=models.ManyToManyField(related_name='birthdatesource', null=True, through='gcd.BirthDateSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_month_source',
            field=models.ManyToManyField(related_name='birthmonthsource', null=True, through='gcd.BirthMonthSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_province_source',
            field=models.ManyToManyField(related_name='birthprovincesource', null=True, through='gcd.BirthProvinceSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='birth_year_source',
            field=models.ManyToManyField(related_name='birthyearsource', null=True, through='gcd.BirthYearSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_city_source',
            field=models.ManyToManyField(related_name='deathcitysource', null=True, through='gcd.DeathCitySource', to='gcd.SourceType', blank=True),
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
            name='death_country_source',
            field=models.ManyToManyField(related_name='deathcountrysource', null=True, through='gcd.DeathCountrySource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_date_source',
            field=models.ManyToManyField(related_name='deathdatesource', null=True, through='gcd.DeathDateSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_month_source',
            field=models.ManyToManyField(related_name='deathmonthsource', null=True, through='gcd.DeathMonthSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_province_source',
            field=models.ManyToManyField(related_name='deathprovincesource', null=True, through='gcd.DeathProvinceSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='death_year_source',
            field=models.ManyToManyField(related_name='deathyearsource', null=True, through='gcd.DeathYearSource', to='gcd.SourceType', blank=True),
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
            name='portrait_source',
            field=models.ManyToManyField(related_name='portraitsource', null=True, through='gcd.PortraitSource', to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='creator',
            name='schools',
            field=models.ManyToManyField(related_name='schoolinformation', null=True, through='gcd.CreatorSchoolDetail', to='gcd.School', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthyearsource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbirthyearsource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthyearsource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbirthyearsourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthprovincesource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbirthprovincesource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthprovincesource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbirthprovincesourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthmonthsource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbirthmonthsource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthmonthsource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbirthmonthsourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthdatesource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbirthdatesource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthdatesource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbirthdatesourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthcountrysource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbirthcountrysource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthcountrysource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbirthcountrysourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthcitysource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbirthcitysource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='birthcitysource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbirthcitysourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='biosource',
            name='creator',
            field=models.ForeignKey(related_name='creatorbiosource', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='biosource',
            name='source_type',
            field=models.ForeignKey(related_name='creatorbiosourcetype', to='gcd.SourceType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='award_source',
            field=models.ManyToManyField(related_name='awardsource', null=True, to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='award',
            name='creator',
            field=models.ForeignKey(to='gcd.Creator'),
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
            name='influence_link',
            field=models.ForeignKey(related_name='exist_influencer', blank=True, to='gcd.Creator', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='artinfluence',
            name='influence_source',
            field=models.ManyToManyField(related_name='influencesource', null=True, to='gcd.SourceType', blank=True),
            preserve_default=True,
        ),
    ]
