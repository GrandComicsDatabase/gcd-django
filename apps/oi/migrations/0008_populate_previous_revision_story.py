# -*- coding: utf-8 -*-
# based on http://reviews.comics.org/r/1492/


from django.db import migrations
from apps.oi import states
from apps.oi import states
from datetime import datetime

DATES = ['2003-01-01',
         '2010-01-01',
         '2013-01-01',
         '2016-01-01',
         '2019-01-01']


def migrate_prev_rev(apps, schema_editor):
    source_name = 'story'
    model = 'StoryRevision'
    m = apps.get_model("oi", model)
    earlier = datetime.strptime('2001-01-01','%Y-%M-%d')
    for date in DATES:
        later = datetime.strptime(date,'%Y-%M-%d')
        # iterator avoids larger memory use, check for need & speed
        for r in m.objects.filter(created__gt=earlier, created__lte=later)\
                          .order_by('created', 'id')\
                          .prefetch_related('changeset').iterator():
            # Two models already have previous_revision set.
            if r.changeset.state != states.DISCARDED:
                # We're going from oldest to newest, so all possible
                # previous revisions should have committed set already.
                # Unless something's gone horribly wrong, it shouldn't
                # matter whether we order by id or modification time,
                # besides concerning the imported old log history
                #
                # DISCARDED revisions do not keep a previous_revision
                #
                # Note that source_name wouldn't always be correct for
                # ReprintRevision, but we don't need to migrate it so
                # that is fine.  The rest of the names are predictable.
                prev = m.objects.filter(**{source_name:
                                           getattr(r, source_name)}) \
                                .filter(committed=True,
                                        created__lte=r.created) \
                                .order_by('-created', '-id')
                if prev.exists():
                    r.previous_revision = prev[0]

            if r.changeset.state == states.APPROVED:
                r.committed = True
            elif r.changeset.state == states.DISCARDED:
                r.committed = False
            r.save()
        earlier = later


def unmigrate_prev_rev(apps, schema_editor):
    StoryRevision.objects.update(committed=None)
    StoryRevision.objects.update(previous_revision=None)


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0007_populate_previous_revision'),
    ]

    operations = [
        migrations.RunPython(migrate_prev_rev,
                             unmigrate_prev_rev),
    ]
