# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0006_auto_20170615_1945'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='creatorrevision',
            name='degrees',
        ),
        migrations.RemoveField(
            model_name='creatorrevision',
            name='schools',
        ),
        migrations.AlterField(
            model_name='creatordegreedetailrevision',
            name='creator',
            field=models.ForeignKey(related_name='degree_revisions', to='gcd.Creator'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='creatorschooldetailrevision',
            name='creator',
            field=models.ForeignKey(related_name='school_revisions', to='gcd.Creator'),
            preserve_default=True,
        ),
    ]
