# Generated by Django 4.2.20 on 2025-05-01 10:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0060_remove_storygroup_group'),
    ]

    operations = [
        migrations.RenameField(
            model_name='feature',
            old_name='year_created',
            new_name='year_first_published',
        ),
        migrations.RenameField(
            model_name='feature',
            old_name='year_created_uncertain',
            new_name='year_first_published_uncertain',
        ),
    ]
