"""Tests for the deterministic local-development data command."""

from django.contrib.auth.models import User
from django.core.management import call_command

from apps.indexer.models import Indexer
from apps.stats.models import CountStats


def test_seed_development_data_is_idempotent_and_initializes_stats(db):
    """Contributors can rerun setup without duplicating accounts or statistics."""
    call_command('seed_development_data')
    call_command('seed_development_data')

    assert User.objects.filter(username='admin').count() == 1
    assert User.objects.filter(username='editor').count() == 1
    assert User.objects.filter(username='anon').count() == 1
    assert Indexer.objects.filter(user__username='admin').exists()
    assert CountStats.objects.filter(language=None, country=None).count() == 8
