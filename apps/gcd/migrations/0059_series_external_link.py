# Generated by Django 4.2.20 on 2025-04-20 06:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0058_publisher_external_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='series',
            name='external_link',
            field=models.ManyToManyField(to='gcd.externallink'),
        ),
    ]
