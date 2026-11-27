"""The sample Latin script has the id of Latin on the site, the default
script of a creator name, so the creator form of a local site works."""

import pytest

from django.core.management import call_command

from apps.gcd.models import CreatorNameDetail
from apps.oi.forms.creator import CreatorRevisionFormSet
from apps.stddata.models import Script

SAMPLE_CREATOR = '[GCD DEV] Alex Example'


@pytest.mark.django_db
def test_the_sample_creator_name_is_in_latin_at_its_site_id():
    """The sample name is in the script with the id Script.LATIN_PK."""
    call_command('seed_development_data')
    name = CreatorNameDetail.objects.get(name=SAMPLE_CREATOR)

    assert name.in_script_id == Script.LATIN_PK
    assert name.in_script.name == 'Latin'


@pytest.mark.django_db
def test_the_blank_name_row_of_the_creator_form_selects_latin():
    """The blank row shows its default script selected, so a browser sends
    it back unchanged and the row is not checked as a new name."""
    call_command('seed_development_data')
    blank_row = CreatorRevisionFormSet().forms[0]

    assert (f'<option value="{Script.LATIN_PK}" selected>Latin</option>'
            in str(blank_row['in_script']))


@pytest.mark.django_db
def test_seeding_uses_the_latin_script_of_the_reference_data():
    """With the scripts of the site, as after a dump, none is added."""
    call_command('loaddata', 'script')
    scripts = Script.objects.count()

    call_command('seed_development_data')

    assert Script.objects.count() == scripts
    name = CreatorNameDetail.objects.get(name=SAMPLE_CREATOR)
    assert name.in_script_id == Script.LATIN_PK


@pytest.mark.django_db
def test_seeding_again_adds_no_script():
    """A second run finds the sample Latin script again."""
    call_command('seed_development_data')

    call_command('seed_development_data')

    assert list(Script.objects.filter(name='Latin').values_list(
      'pk', flat=True)) == [Script.LATIN_PK]
