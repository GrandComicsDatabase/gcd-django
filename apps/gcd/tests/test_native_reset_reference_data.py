"""Native reset must leave the migrated schema ready for sample setup."""

import re
import shlex
from pathlib import Path

import pytest
from django.apps import apps
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from apps.gcd.models import Publisher, Series
from apps.stddata.models import Country


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_native_reset_management_sequence_can_seed_again(settings, tmp_path):
    """Replay actual reset commands only inside Django's disposable test DB."""
    assert connection.settings_dict['NAME'].startswith('test_')
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    call_command('seed_development_data', verbosity=0)
    assert Series.objects.filter(name='[GCD DEV] Adventures').exists()
    before = set(MigrationRecorder(connection).applied_migrations())

    native_reset = (ROOT / 'bin/dev').read_text().split('  reset)\n')[1]
    native_reset = native_reset.split('    else\n', 1)[1]
    commands = re.findall(
        r'^\s*"\$PYTHON_BIN" manage\.py (.+)$', native_reset, re.MULTILINE,
    )
    assert commands[:2] == ['flush --noinput', 'migrate --noinput']
    for arguments in commands:
        call_command(*shlex.split(arguments), verbosity=0)

    assert not Series.objects.exists()
    assert set(MigrationRecorder(connection).applied_migrations()) == before
    call_command('seed_development_data', verbosity=0)
    assert Series.objects.filter(name='[GCD DEV] Adventures').exists()
    for username, password in (
        ('admin', 'admin'), ('editor', 'editme'), ('dexter_1234', 'test'),
    ):
        assert authenticate(username=username, password=password) is not None
    # Initial data migrations, not just the sample's immediate dependencies.
    for label in (
        'stddata.Country', 'stddata.Currency', 'stddata.Language',
        'gcd.ImageType', 'gcd.StoryType', 'gcd.SeriesBondType',
        'gcd.SeriesPublicationType', 'gcd.Degree', 'gcd.MembershipType',
        'gcd.NameType', 'gcd.NonComicWorkRole', 'gcd.NonComicWorkType',
        'gcd.RelationType', 'gcd.School', 'gcd.SourceType',
        'mycomics.ConditionGradeScale', 'mycomics.ConditionGrade',
        'voting.VoteType',
    ):
        assert apps.get_model(label).objects.exists(), label


@pytest.mark.django_db
def test_reference_restore_preserves_populated_tables_and_local_catalog():
    country = Country.objects.get(code='us')
    country.name = 'Local country name must survive'
    country.save(update_fields=['name'])
    publisher = Publisher.objects.create(
        name='Unrelated preserved publisher', country=country,
    )
    original_countries = list(Country.objects.values().order_by('pk'))
    call_command('restore_development_reference_data', verbosity=0)
    assert list(Country.objects.values().order_by('pk')) == original_countries
    assert Publisher.objects.get(pk=publisher.pk).name == publisher.name


@pytest.mark.django_db
def test_reference_restore_rolls_back_on_fixture_failure(monkeypatch):
    from apps.gcd.management.commands import restore_development_reference_data

    Country.objects.all().delete()
    currency_model = apps.get_model('stddata.Currency')
    currency_model.objects.all().delete()

    def fail_on_currency(command, fixture, **options):
        if fixture == 'currency':
            raise RuntimeError('fixture failure')
        return call_command(command, fixture, **options)

    monkeypatch.setattr(
        restore_development_reference_data, 'call_command', fail_on_currency,
    )
    with pytest.raises(RuntimeError, match='fixture failure'):
        call_command('restore_development_reference_data', verbosity=0)
    assert not Country.objects.exists()
    assert not currency_model.objects.exists()
