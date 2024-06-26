# Generated by Django 3.2.24 on 2024-03-31 07:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0054_use_group_name_in_sequence'),
        ('oi', '0051_group_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='storycharacterrevision',
            name='group_name',
            field=models.ManyToManyField(blank=True, to='gcd.GroupNameDetail'),
        ),
        migrations.AddField(
            model_name='storygrouprevision',
            name='group_name',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gcd.groupnamedetail'),
        ),
        migrations.AlterField(
            model_name='storygrouprevision',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='story_group_revisions', to='gcd.group'),
        ),
    ]
