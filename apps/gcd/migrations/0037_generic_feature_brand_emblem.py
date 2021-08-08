# Generated by Django 2.2.20 on 2021-06-19 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0036_creator_disambiguation'),
    ]

    operations = [
        migrations.AddField(
            model_name='brand',
            name='generic',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='featurelogo',
            name='generic',
            field=models.BooleanField(default=False),
        ),
    ]