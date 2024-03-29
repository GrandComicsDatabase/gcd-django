# Generated by Django 3.2.19 on 2023-10-28 12:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0052_add_universe_for_group'),
        ('oi', '0049_add_multiverse'),
    ]

    operations = [
        migrations.AddField(
            model_name='grouprevision',
            name='universe',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='group_revisions', to='gcd.universe'),
        ),
        migrations.AddField(
            model_name='storycharacterrevision',
            name='group_universe',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='story_character_in_group_revision', to='gcd.universe'),
        ),
        migrations.AddField(
            model_name='storygrouprevision',
            name='universe',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='gcd.universe'),
        ),
    ]
