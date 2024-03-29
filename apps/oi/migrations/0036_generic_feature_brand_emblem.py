# Generated by Django 2.2.20 on 2021-06-19 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0035_creator_disambiguation'),
    ]

    operations = [
        migrations.AddField(
            model_name='brandrevision',
            name='generic',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='featurelogorevision',
            name='generic',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='creatorrevision',
            name='disambiguation',
            field=models.CharField(blank=True, db_index=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='issuecreditrevision',
            name='credit_name',
            field=models.CharField(max_length=255),
        ),
    ]
