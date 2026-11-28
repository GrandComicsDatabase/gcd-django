# -*- coding: utf-8 -*-
"""A button puts the title of a sequence or an issue in title case."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from django.conf import settings
from django.urls import reverse

from apps.oi.models import CTYPES
from apps.stddata.models import Language

TITLE_CASE_JS = Path(settings.STATICFILES_DIRS[0], 'js', 'oi', 'title_case.js')
NODE = shutil.which('node')
# loads the script and prints toTitleCase of each title read from stdin
RUN_SCRIPT = (
    "const fs = require('fs');"
    "require('vm').runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));"
    "const titles = JSON.parse(fs.readFileSync(0, 'utf8'));"
    "console.log(JSON.stringify(titles.map(toTitleCase)));")


@pytest.fixture
def indexer_client(client, any_indexer):
    """A logged in indexer with superuser rights."""
    any_indexer.is_superuser = True
    any_indexer.save()
    client.force_login(any_indexer)
    return client


def _edit_page(client, story_revision, model_name):
    """Return the edit page and the label of its title field."""
    # the edit page of a sequence is that of a change to its issue
    changeset = story_revision.changeset
    changeset.change_type = CTYPES['issue']
    changeset.save()
    revision = {'story': story_revision,
                'issue': changeset.issuerevisions.get()}[model_name]
    url = reverse('edit_revision', kwargs={'model_name': model_name,
                                           'id': revision.id})
    response = client.get(url)

    assert response.status_code == 200
    page = response.content.decode()
    label = re.search(r'<label for="id_title"[^>]*>(.*?)</label>', page,
                      re.S)
    assert label
    return page, label.group(1)


@pytest.mark.django_db
@pytest.mark.parametrize('model_name', ['story', 'issue'])
def test_title_has_title_case_button(indexer_client, any_edit_story_rev,
                                     model_name):
    """The title of a series in English has the button."""
    series = any_edit_story_rev.issue.series
    series.language = Language.objects.get_or_create(
      code='en', defaults={'name': 'English'})[0]
    series.save()
    # both forms read the language from this series
    assert any_edit_story_rev.changeset.issuerevisions.get().series == series

    page, label = _edit_page(indexer_client, any_edit_story_rev, model_name)

    # the button sits in the label and changes the field of the label
    assert re.search(
      r'<button type="button" [^>]*onclick="[^"]*'
      r'this\.parentElement\.control[^"]*toTitleCase\(', label)
    # the rule of the button comes from a static script
    assert 'src="/static/js/oi/title_case.js"' in page
    # only the title has it: the feature keeps the spelling it is given
    assert page.count('toTitleCase(') == 1


@pytest.mark.django_db
@pytest.mark.parametrize('model_name', ['story', 'issue'])
def test_title_has_no_button_in_another_language(
        indexer_client, any_edit_story_rev, model_name):
    """The button knows only the English rules."""
    assert any_edit_story_rev.issue.series.language.code != 'en'

    _, label = _edit_page(indexer_client, any_edit_story_rev, model_name)

    assert '<button' not in label
    assert label.strip().startswith('Title')


@pytest.mark.skipif(NODE is None, reason='the script runs in Node.js')
@pytest.mark.parametrize('typed, expected', [
    # prepositions of fewer than five letters stay in lower case
    ('journey up the river', 'Journey up the River'),
    ('war over the world', 'War over the World'),
    ('the house near the sea', 'The House near the Sea'),
    ('a step off the edge', 'A Step off the Edge'),
    ('the man down the hall', 'The Man down the Hall'),
    ('a walk past the gate', 'A Walk past the Gate'),
    ('from dusk till dawn', 'From Dusk till Dawn'),
    ('a day like no other', 'A Day like No Other'),
    ('running with scissors', 'Running with Scissors'),
    # prepositions of five or more letters get a capital
    ('a dialogue between the soul and body',
     'A Dialogue Between the Soul and Body'),
    # so does the first word of a compound preposition
    ('time out of mind', 'Time Out of Mind'),
    # and a short word with no object after it, here an adverb
    ('go down, moses', 'Go Down, Moses'),
])
def test_prepositions_get_a_capital_from_five_letters(typed, expected):
    """The wiki capitalizes only the prepositions of five or more letters."""
    result = subprocess.run([NODE, '-e', RUN_SCRIPT, str(TITLE_CASE_JS)],
                            input=json.dumps([typed]), capture_output=True,
                            text=True, check=True)

    assert json.loads(result.stdout) == [expected]
