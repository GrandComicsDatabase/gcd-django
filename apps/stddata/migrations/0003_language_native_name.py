# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stddata', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='language',
            name='native_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
