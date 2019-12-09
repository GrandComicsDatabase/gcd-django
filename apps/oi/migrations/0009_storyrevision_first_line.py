# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0008_populate_previous_revision_story'),
    ]

    operations = [
        migrations.AddField(
            model_name='storyrevision',
            name='first_line',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
