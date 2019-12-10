# -*- coding: utf-8 -*-


from django.db import migrations
from django.core.management import call_command
from django.contrib.sites.models import Site


def load_initial_data(apps, schema_editor):
    # Only load if not already present- this is to support running the
    # migrations with --fake-initial to upgrade from South.
    if not Site.objects.exists():
        call_command('loaddata', 'site')

    for model in ('ImageType', 'StoryType', 'SeriesBondType',
                  'SeriesPublicationType'):
        if not apps.get_model('gcd', model).objects.exists():
            call_command('loaddata', model.lower())


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0001_initial'),
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_initial_data),
    ]
