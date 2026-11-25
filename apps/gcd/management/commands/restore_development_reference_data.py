"""Restore empty migration-owned reference tables after a development flush."""

from django.apps import apps
from django.core.management import BaseCommand, call_command
from django.db import transaction


# Match the reference fixtures loaded by the initial-data migrations. Flush
# preserves the migration ledger, so migrate alone does not load these again.
# Keep dependency order: condition grades refer to their scales.
REFERENCE_FIXTURES = (
    ('stddata.Country', 'country'),
    ('stddata.Currency', 'currency'),
    ('stddata.Language', 'language'),
    ('sites.Site', 'site'),
    ('gcd.ImageType', 'imagetype'),
    ('gcd.StoryType', 'storytype'),
    ('gcd.SeriesBondType', 'seriesbondtype'),
    ('gcd.SeriesPublicationType', 'seriespublicationtype'),
    ('gcd.Degree', 'degree'),
    ('gcd.MembershipType', 'membershiptype'),
    ('gcd.NameType', 'nametype'),
    ('gcd.NonComicWorkRole', 'noncomicworkrole'),
    ('gcd.NonComicWorkType', 'noncomicworktype'),
    ('gcd.RelationType', 'relationtype'),
    ('gcd.School', 'school'),
    ('gcd.SourceType', 'sourcetype'),
    ('mycomics.ConditionGradeScale', 'conditiongradescale'),
    ('mycomics.ConditionGrade', 'conditiongrade'),
    ('voting.VoteType', 'vote-types'),
)


class Command(BaseCommand):
    help = (
        'Restore empty reference tables after native development reset. '
        'Populated reference tables and catalog records are not overwritten.'
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            for label, fixture in REFERENCE_FIXTURES:
                if not apps.get_model(label).objects.exists():
                    call_command(
                        'loaddata', fixture, verbosity=options['verbosity'],
                    )
        self.stdout.write('Development reference data is ready.')
