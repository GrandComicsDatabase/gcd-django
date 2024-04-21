# -*- coding: utf-8 -*-
# based on http://reviews.comics.org/r/1492/


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
              #StoryRevision is too large, separate
              #'StoryRevision',
              'ReprintRevision',
              'ImageRevision',
              'AwardRevision',
              'DataSourceRevision',
              'CreatorRevision',
              'CreatorArtInfluenceRevision',
              'CreatorAwardRevision',
              'CreatorDegreeRevision',
              'CreatorMembershipRevision',
              'CreatorNameDetailRevision',
              'CreatorNonComicWorkRevision',
              'CreatorRelationRevision',
              'CreatorSchoolRevision')

def migrate_prev_rev(apps, schema_editor):
    for model in MODEL_LIST:
        display_model = model[0:model.find('Revision')]
        source_name = ''
        for char in display_model:
            if char.isupper() and source_name:
                source_name = '%s_%s' % (source_name, char.lower())
            else:
                source_name = '%s%s' % (source_name, char.lower())
        m = apps.get_model("oi", model)
        # iterator avoids larger memory use, TODO check for need & speed
        for r in m.objects.order_by('created', 'id') \
                          .prefetch_related('changeset').iterator():
            # Two models already have previous_revision set.
            if (model not in ('SeriesBondRevision', 'ReprintRevision') and
                    r.changeset.state != states.DISCARDED):
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


def unmigrate_prev_rev(apps, schema_editor):
    for model in MODEL_LIST:
        m = apps.get_model("oi", model)
        m.objects.update(committed=None)
        if model not in ('SeriesBondRevision', 'ReprintRevision'):
            m.objects.update(previous_revision=None)


class Migration(migrations.Migration):

    dependencies = [
        ('oi', '0006_previous_revision_for_all'),
        ('gcd', '0006_add_GcdData_and_model_cleanup'),
    ]

    operations = [
        migrations.RunPython(migrate_prev_rev,
                             unmigrate_prev_rev),
    ]
