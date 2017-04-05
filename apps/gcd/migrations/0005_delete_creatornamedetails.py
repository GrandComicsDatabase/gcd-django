# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0004_CreatorNameDetail'),
        ('oi', '0003_CreatorNameDetail'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CreatorNameDetails',
        ),
    ]
