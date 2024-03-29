# Generated by Django 3.2.19 on 2023-09-30 15:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0044_feature_disambiguation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='featurerevision',
            name='disambiguation',
            field=models.CharField(blank=True, db_index=True, default='', help_text='If needed a short phrase for the disambiguation of features with a similar or identical name.', max_length=255),
        ),
        migrations.AlterField(
            model_name='issuerevision',
            name='variant_cover_status',
            field=models.IntegerField(choices=[(1, 'No Difference'), (2, 'Only Scan Difference'), (3, 'Artwork Difference')], db_index=True, default=3),
        ),
    ]
