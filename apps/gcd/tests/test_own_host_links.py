"""The site links its own hosts with https, not with http."""
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.indexer.models import Indexer
from apps.mycomics.models import ConditionGradeScale
from apps.stddata.models import Country, Language

ROOT = Path(__file__).resolve().parents[3]

# www, my, docs, beta and errors, the hosts of the GCD itself
OWN_HOST_HTTP = re.compile(
  r'http://(?:www\.|docs\.|my\.|beta\.|errors\.)?comics\.org')

TEXT_SUFFIXES = {'.html', '.txt', '.xml', '.po', '.md', '.py'}


def _site_files():
    """The files with a suffix of TEXT_SUFFIXES under templates, static,
    locale and apps, without tests and migrations."""
    for folder in ('templates', 'static', 'locale', 'apps'):
        for path in (ROOT / folder).rglob('*'):
            parts = path.relative_to(ROOT).parts
            if path.suffix in TEXT_SUFFIXES and path.is_file() and \
               'tests' not in parts and 'migrations' not in parts:
                yield path


def test_own_hosts_are_linked_with_https():
    """No template, translation, code or other file of those suffixes
    links the GCD's own hosts with http."""
    found = ['%s:%d' % (path.relative_to(ROOT), number)
             for path in _site_files()
             for number, line in enumerate(
               path.read_text(encoding='utf-8', errors='replace')
                   .splitlines(), 1)
             if OWN_HOST_HTTP.search(line)]

    assert found == []


@pytest.mark.django_db
def test_mentor_link_of_the_new_indexer_mail_uses_https(client,
                                                        mailoutbox):
    """The mail about a new indexer links the mentor page with https on
    the host the account was confirmed on."""
    ConditionGradeScale.objects.get_or_create(
      pk=1, defaults={'name': 'Test scale'})
    Language.objects.get_or_create(code='en',
                                   defaults={'name': 'English'})
    country = Country.objects.get_or_create(code='XZZ',
                                            name='Test Country')[0]
    user = User.objects.create_user('new_indexer', is_active=False)
    Indexer.objects.create(user=user, country=country,
                           registration_key='0a1b2c',
                           registration_expires=date.today() +
                           timedelta(days=1))

    client.get(reverse('confirm', kwargs={'key': '0a1b2c'}))

    mentor = reverse('mentor', kwargs={'user_id': user.id})
    [mail] = [sent for sent in mailoutbox
              if sent.subject.startswith('New Indexer')]
    assert 'Mentor this indexer: https://testserver%s' % mentor in mail.body
