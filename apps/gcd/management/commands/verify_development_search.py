"""Verify the optional development search stack end to end."""

import time
import uuid

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from haystack import connections
from haystack.query import SearchQuerySet

from apps.gcd.models import Publisher, Series


SAMPLE_SERIES_NAME = '[GCD DEV] Adventures'
QUEUE_TIMEOUT_SECONDS = 30


class Command(BaseCommand):
    """Check search queries and queued index updates against sample data."""

    help = (
        'Verify Elasticsearch connectivity, the sample index, and queued '
        'save/delete updates in the development search environment.'
    )

    def handle(self, *args, **options):
        """Run checks and report the observed Elasticsearch state."""
        if not settings.USE_ELASTICSEARCH:
            raise CommandError(
                'Search is disabled. Start it with ./bin/dev search-rebuild.'
            )

        backend = connections['default'].get_backend()
        info = backend.conn.info()
        version = info['version']['number']
        if not version.startswith('7.'):
            raise CommandError(
                f'Expected Elasticsearch 7.x, but found {version}.'
            )

        try:
            series = Series.objects.get(name=SAMPLE_SERIES_NAME)
        except Series.DoesNotExist as error:
            raise CommandError(
                'The deterministic sample data is missing. Run ./bin/dev '
                'setup before verifying search.'
            ) from error

        if not self._is_indexed(Series, series.pk):
            raise CommandError(
                f'{SAMPLE_SERIES_NAME} is missing from the search index.'
            )

        self._verify_queued_updates(series.publisher)
        document_count = backend.conn.count(index=backend.index_name)['count']
        self.stdout.write(
            self.style.SUCCESS(
                f'Elasticsearch {version} is ready with {document_count} '
                'documents; queued save/delete updates passed.'
            )
        )

    def _verify_queued_updates(self, sample_publisher):
        """Create and delete a probe, waiting for both queued index changes."""
        probe = Publisher.objects.create(
            name=f'[GCD DEV] Search Queue Probe {uuid.uuid4().hex}',
            country=sample_publisher.country,
        )
        probe_pk = probe.pk

        try:
            self._wait_until(
                lambda: self._is_indexed(Publisher, probe_pk),
                'The queued publisher save did not reach Elasticsearch.',
            )
            probe.delete()
            self._wait_until(
                lambda: not self._is_indexed(Publisher, probe_pk),
                'The queued publisher delete did not reach Elasticsearch.',
            )
        finally:
            Publisher.objects.filter(pk=probe_pk).delete()

    @staticmethod
    def _is_indexed(model, object_id):
        """Return whether an object identifier is visible in Haystack."""
        return SearchQuerySet().models(model).filter(
            django_id=str(object_id)
        ).count() > 0

    @staticmethod
    def _wait_until(predicate, failure_message):
        """Poll an asynchronous result until it is visible or times out."""
        deadline = time.monotonic() + QUEUE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.5)
        raise CommandError(failure_message)
