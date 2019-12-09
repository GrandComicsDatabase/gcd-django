# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0004_initial_creator_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='volume_not_printed',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
