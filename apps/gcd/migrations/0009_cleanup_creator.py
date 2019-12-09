# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0008_move_first_line_from_title'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='creator',
            name='degrees',
        ),
        migrations.RemoveField(
            model_name='creator',
            name='schools',
        ),
    ]
