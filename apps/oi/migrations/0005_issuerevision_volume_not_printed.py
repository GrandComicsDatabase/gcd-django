# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0004_creators'),
    ]

    operations = [
        migrations.AddField(
            model_name='issuerevision',
            name='volume_not_printed',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
