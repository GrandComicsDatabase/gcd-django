# Generated by Django 3.2.19 on 2023-10-28 12:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0051_add_multiverse'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='universe',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gcd.universe'),
        ),
        migrations.AddField(
            model_name='storycharacter',
            name='group_universe',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='story_character_in_group', to='gcd.universe'),
        ),
        migrations.AddField(
            model_name='storygroup',
            name='universe',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gcd.universe'),
        ),
        migrations.AlterField(
            model_name='character',
            name='universe',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gcd.universe'),
        ),
    ]
