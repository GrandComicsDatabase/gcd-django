# Generated by Django 3.2.19 on 2023-10-21 07:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0050_storygroup'),
        ('oi', '0047_characterrevision_universe'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoryGroupRevision',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('committed', models.BooleanField(db_index=True, default=None, null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('notes', models.TextField(blank=True)),
                ('changeset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storygrouprevisions', to='oi.changeset')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='story_group_revisions', to='gcd.group')),
                ('previous_revision', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='next_revision', to='oi.storygrouprevision')),
                ('story_group', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='gcd.storygroup')),
                ('story_revision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='story_group_revisions', to='oi.storyrevision')),
            ],
            options={
                'db_table': 'oi_story_group_revision',
                'ordering': ['group__sort_name'],
            },
        ),
    ]
