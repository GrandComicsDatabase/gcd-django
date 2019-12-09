# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0006_add_GcdData_and_model_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='first_line',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
    ]
