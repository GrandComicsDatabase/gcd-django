# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from apps.oi import states


MODEL_LIST = ('PublisherRevision',
              'IndiciaPublisherRevision',
              'BrandGroupRevision',
              'BrandRevision',
              'BrandUseRevision',
              'CoverRevision',
              'SeriesRevision',
              'SeriesBondRevision',
              'IssueRevision',
              'StoryRevision',
              'ReprintRevision',
              'ImageRevision')


def migrate_prev_committed(apps, schema_editor):
    for model in MODEL_LIST:
        display_model = model[0:model.find('Revision')]
        source_name = ''
        for char in display_model:
            if char.isupper() and source_name:
                source_name = '%s_%s' % (source_name, char.lower())
            else:
                source_name = '%s%s' % (source_name, char.lower())

        m = apps.get_model("oi", model)
        for r in m.objects.order_by('created', 'id') \
                          .prefetch_related('changeset'):
            # Two models already have previous_revision set.
            if (model not in ('SeriesBondRevision', 'ReprintRevision') and
                    r.changeset.state != states.DISCARDED):
                # We're going from oldest to newest, so all possible
                # prevoius revisions should have committed set already.
                # Unless something's gone horribly wrong, it shouldn't
                # matter whether we order by id or modification time.
                #
                # Note that source_name wouldn't always be correct for
                # ReprintRevision, but we don't need to migrate it so
                # that is fine.  The rest of the names are predictable.
                prev = m.objects.filter(**{source_name:
                                           getattr(r, source_name)}) \
                                .filter(committed=True, id__lt=r.id) \
                                .order_by('-created', '-id')
                if prev.exists():
                    r.previous_revision = prev[0]

            if r.changeset.state == states.APPROVED:
                r.committed = True
            elif r.changeset.state == states.DISCARDED:
                r.committed = False

            r.save()


def unmigrate_prev_committed(apps, schema_editor):
    for model in MODEL_LIST:
        m = apps.get_model("oi", model)
        m.objects.update(committed=None)
        if model not in ('SeriesBondRevision', 'ReprintRevision'):
            m.objects.update(previous_revision=None)


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0002_add_previous_revision'),
    ]

    operations = [
        migrations.RunPython(migrate_prev_committed,
                             unmigrate_prev_committed),
    ]
