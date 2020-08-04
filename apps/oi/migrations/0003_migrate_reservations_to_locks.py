# -*- coding: utf-8 -*-


from django.db import models, migrations

# from django.contrib.contenttypes.management import update_contenttypes
# in 1.11 use instead create_contenttypes

from apps.oi import states

RESERVABLE_CLASSES = (
    'Publisher',
    'IndiciaPublisher',
    'BrandGroup',
    'Brand',
    'BrandUse',

    'Series',
    'Issue',
    'Story',
    'Cover',
    'Image',

    'SeriesBond',
    'Reprint',
    'IssueReprint',
    'ReprintFromIssue',
    'ReprintToIssue',

)

def migrate_reservation_to_lock(apps, schema_editor):
    # For fresh db might need to ensure ContentType objects exist at this point:
    #app_config = apps.get_app_config('gcd')
    #app_config.models_module = app_config.models_module or True
    #update_contenttypes(app_config)
    
    RevisionLock = apps.get_model('oi', 'RevisionLock')

    for classname in RESERVABLE_CLASSES:
        # We can't import the model directly as it may be a newer version
        # than this migration expects. We use the historical version.
        obj_class = apps.get_model('gcd', classname)
        if classname == 'Story':
            objects = obj_class.objects.filter(issue__reserved=True,
                                               deleted=False)
        else:
            objects = obj_class.objects.filter(reserved=True)
        for obj in objects:
            rev = obj.revisions.get(changeset__state__in=states.ACTIVE)

            ContentType = apps.get_model('contenttypes', 'ContentType')

            ct = ContentType.objects.get(app_label='gcd',
                                         model=classname.lower())

            lock = RevisionLock(changeset=rev.changeset,
                                object_id=obj.id,
                                content_type=ct)
            lock.save()


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0002_revision_lock'),
        ('gcd', '0002_initial_data'),
        #('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_reservation_to_lock)
    ]
