# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0002_initial_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mailinglist',
            name='address',
            field=models.EmailField(max_length=254),
        ),
    ]
