"""Create the small, deterministic dataset used for local development."""

from django.core.management import BaseCommand, call_command
from django.db import transaction

from apps.stats.models import CountStats


class Command(BaseCommand):
    """Load local accounts and the statistics required by edit workflows."""

    help = (
        'Load deterministic development accounts and initialize global '
        'catalog statistics.'
    )

    def handle(self, *args, **options):
        """Seed data safely on a new database or refresh it on an existing one."""
        with transaction.atomic():
            call_command('loaddata', 'users', verbosity=options['verbosity'])
            CountStats.objects.init_stats()

        self.stdout.write(
            self.style.SUCCESS('Development accounts and catalog statistics are ready.')
        )
