# Generated by Django 2.2.12 on 2020-06-11 15:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0030_indicia_printer_per_issue'),
    ]

    operations = [
        migrations.AddField(
            model_name='storycredit',
            name='signature',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='credits', to='gcd.CreatorSignature'),
        ),
    ]
