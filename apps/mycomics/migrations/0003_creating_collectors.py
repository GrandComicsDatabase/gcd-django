# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db import IntegrityError


def create_collector(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Collector = apps.get_model("mycomics", "Collector")
    Collection = apps.get_model("mycomics", "Collection")
    ConditionGradeScale = apps.get_model("mycomics", "ConditionGradeScale")
    Language = apps.get_model("gcd", "Language")

    for user in User.objects.filter(is_active=True):
        try:
            collector = Collector(user=user)
            collector.grade_system = ConditionGradeScale.objects.get(pk=1)
            collector.default_language = Language.objects.get(code='en')
            collector.save()

            default_have_collection = Collection(
                collector=collector,
                name='Default have collection',
                condition_used=True,
                acquisition_date_used=True,
                location_used=True,
                purchase_location_used=True,
                was_read_used=True,
                for_sale_used=True,
                signed_used=True,
                price_paid_used=True,
                own_used=True,
                own_default=True)
            default_have_collection.save()

            default_want_collection = Collection(
                collector=collector,
                name='Default want collection',
                market_value_used=True,
                own_used=True,
                own_default=False)
            default_want_collection.save()

            collector.default_have_collection = default_have_collection
            collector.default_want_collection = default_want_collection
            collector.save()

        except IntegrityError:
            # There probably already is a Collector entry for this user
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('mycomics', '0002_load_initial_fixture'),
        ('gcd', '0002_initial_data'),
    ]

    operations = [
        migrations.RunPython(create_collector),
    ]
