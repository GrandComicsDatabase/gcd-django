"""The sample creator has birth and death dates, like a creator saved
through the site."""

import pytest

from django.core.management import call_command

from apps.gcd.models import Creator
from apps.stddata.models import Date

SAMPLE_CREATOR = '[GCD DEV] Alex Example'


@pytest.mark.django_db
def test_the_sample_creator_can_be_named():
    call_command('seed_development_data')
    creator = Creator.objects.get(gcd_official_name=SAMPLE_CREATOR)

    assert str(creator) == SAMPLE_CREATOR
    assert creator.death_date.year == ''


@pytest.mark.django_db
def test_seeding_again_adds_no_dates():
    call_command('seed_development_data')
    dates = Date.objects.count()

    call_command('seed_development_data')

    assert Date.objects.count() == dates


@pytest.mark.django_db
@pytest.mark.parametrize('missing', [['birth_date', 'death_date'],
                                     ['death_date']])
def test_seeding_again_completes_a_creator_seeded_before(missing):
    call_command('seed_development_data')
    Creator.objects.filter(gcd_official_name=SAMPLE_CREATOR).update(
      **{field: None for field in missing})

    call_command('seed_development_data')

    creator = Creator.objects.get(gcd_official_name=SAMPLE_CREATOR)
    assert str(creator) == SAMPLE_CREATOR
    assert creator.death_date.year == ''
