"""Tests for the deterministic local-development data command."""

from django.contrib.auth.models import User
from django.core.management import call_command

from apps.gcd.models import (
    Character,
    Cover,
    Creator,
    Feature,
    Group,
    Image,
    Issue,
    Publisher,
    Reprint,
    Series,
    Story,
    StoryCharacter,
    StoryCredit,
    Universe,
)
from apps.indexer.models import Indexer
from apps.oi.models import ChangesetComment
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

    publisher = Publisher.objects.get(name='[GCD DEV] Example Comics')
    series = Series.objects.get(name='[GCD DEV] Adventures', publisher=publisher)
    issue = Issue.objects.get(series=series, sort_code=1)
    variant = Issue.objects.get(series=series, sort_code=2)
    story = Story.objects.get(issue=issue, sequence_number=0)

    assert variant.variant_of == issue
    assert Feature.objects.filter(name='[GCD DEV] Feature').exists()
    assert Creator.objects.filter(gcd_official_name='[GCD DEV] Alex Example').exists()
    assert StoryCredit.objects.filter(story=story).exists()
    assert Universe.objects.filter(designation='Earth-DEV').exists()
    assert Character.objects.filter(name='[GCD DEV] Captain Example').exists()
    assert Group.objects.filter(name='[GCD DEV] Example League').exists()
    assert StoryCharacter.objects.filter(story=story).exists()
    assert Reprint.objects.filter(origin=story, target_issue=variant).exists()
    assert Cover.objects.filter(issue__in=(issue, variant)).count() == 2
    assert Image.objects.filter(object_id__in=(issue.id, variant.id)).exclude(
        image_file=''
    ).count() == 2
    assert ChangesetComment.objects.filter(text__contains='[GCD DEV]').count() == 1
