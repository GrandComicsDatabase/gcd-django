# -*- coding: utf-8 -*-


from django.db import migrations
from django.core.management import call_command
from django.contrib.sites.models import Site


def load_initial_creator_data(apps, schema_editor):
    for model in ('degree', 'membershiptype', 'nametype',
                  'noncomicworkrole', 'noncomicworktype',
                  'relationtype', 'school', 'sourcetype',
                  'imagetype'):
        call_command('loaddata', model.lower())


class Migration(migrations.Migration):

    dependencies = [
        ('gcd', '0003_creators'),
    ]

    operations = [
        migrations.RunPython(load_initial_creator_data),
    ]
