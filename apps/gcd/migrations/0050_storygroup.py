# Generated by Django 3.2.19 on 2023-10-21 07:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0049_character_universe'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoryGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, db_index=True)),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('notes', models.TextField()),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='gcd.group')),
                ('story', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appearing_groups', to='gcd.story')),
            ],
            options={
                'db_table': 'gcd_group_character',
                'ordering': ['group__sort_name'],
            },
        ),
    ]