# Generated by Django 2.2.12 on 2021-01-14 20:32

from django.db import migrations, models
import django.db.models.deletion
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0002_auto_20150616_2121'),
        ('stddata', '0003_script'),
        ('gcd', '0032_housekeeping'),
    ]

    operations = [
        migrations.CreateModel(
            name='Character',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('sort_name', models.CharField(db_index=True, default='', max_length=255)),
                ('disambiguation', models.CharField(db_index=True, max_length=255)),
                ('year_first_published', models.IntegerField(db_index=True, null=True)),
                ('year_first_published_uncertain', models.BooleanField(default=False)),
                ('description', models.TextField()),
                ('notes', models.TextField()),
                ('keywords', taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags')),
                ('language', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='stddata.Language')),
            ],
            options={
                'verbose_name_plural': 'Characters',
                'ordering': ('sort_name', 'created'),
            },
        ),
        migrations.CreateModel(
            name='CharacterRelationType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=50)),
                ('reverse_type', models.CharField(max_length=50)),
            ],
            options={
                'verbose_name_plural': 'Character Relation Types',
                'db_table': 'gcd_character_relation_type',
                'ordering': ('type',),
            },
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('sort_name', models.CharField(db_index=True, default='', max_length=255)),
                ('disambiguation', models.CharField(db_index=True, max_length=255)),
                ('year_first_published', models.IntegerField(db_index=True, null=True)),
                ('year_first_published_uncertain', models.BooleanField(default=False)),
                ('description', models.TextField()),
                ('notes', models.TextField()),
                ('keywords', taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags')),
                ('language', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='stddata.Language')),
            ],
            options={
                'verbose_name_plural': 'Groups',
                'ordering': ('sort_name', 'created'),
            },
        ),
        migrations.CreateModel(
            name='GroupMembershipType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=50)),
                ('reverse_type', models.CharField(max_length=50)),
            ],
            options={
                'verbose_name_plural': 'Group Membership Types',
                'db_table': 'gcd_group_membership_type',
                'ordering': ('type',),
            },
        ),
        migrations.CreateModel(
            name='GroupRelationType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=50)),
                ('reverse_type', models.CharField(max_length=50)),
            ],
            options={
                'verbose_name_plural': 'Group Relation Types',
                'db_table': 'gcd_group_relation_type',
                'ordering': ('type',),
            },
        ),
        migrations.CreateModel(
            name='GroupRelation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('notes', models.TextField()),
                ('from_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_related_group', to='gcd.Group')),
                ('relation_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relation_type', to='gcd.GroupRelationType')),
                ('to_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='from_related_group', to='gcd.Group')),
            ],
            options={
                'verbose_name_plural': 'Group Relations',
                'db_table': 'gcd_group_relation',
                'ordering': ('relation_type', 'to_group', 'from_group'),
            },
        ),
        migrations.CreateModel(
            name='GroupMembership',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('year_joined', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('year_joined_uncertain', models.BooleanField(default=False)),
                ('year_left', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('year_left_uncertain', models.BooleanField(default=False)),
                ('notes', models.TextField()),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='gcd.Character')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='gcd.Group')),
                ('membership_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='gcd.GroupMembershipType')),
            ],
            options={
                'verbose_name_plural': 'Group Memberships',
                'db_table': 'gcd_group_membership',
                'ordering': ('character', 'group', 'membership_type'),
            },
        ),
        migrations.CreateModel(
            name='CharacterRelation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('notes', models.TextField()),
                ('from_character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_related_character', to='gcd.Character')),
                ('relation_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relation_type', to='gcd.CharacterRelationType')),
                ('to_character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='from_related_character', to='gcd.Character')),
            ],
            options={
                'verbose_name_plural': 'Character Relations',
                'db_table': 'gcd_character_relation',
                'ordering': ('relation_type', 'to_character', 'from_character'),
            },
        ),
        migrations.CreateModel(
            name='CharacterNameDetail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('sort_name', models.CharField(db_index=True, default='', max_length=255)),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='character_names', to='gcd.Character')),
            ],
            options={
                'verbose_name_plural': 'CharacterName Details',
                'db_table': 'gcd_character_name_detail',
                'ordering': ['sort_name'],
            },
        ),
    ]
