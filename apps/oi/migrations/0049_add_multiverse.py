# Generated by Django 3.2.19 on 2023-10-21 21:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0051_add_multiverse'),
        ('oi', '0048_storygrouprevision'),
    ]

    operations = [
        migrations.AddField(
            model_name='universerevision',
            name='verse',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='gcd.multiverse'),
        ),
    ]
