"""Tests for the command that runs the regular clean-ups."""

from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import (
    CommandError, call_command, load_command_class)
from taggit.models import Tag, TaggedItem

TASKS = 'apps.gcd.management.commands.regular_tasks.TASKS'
CRON_LINE = ('15 4 * * * cd <site> && python manage.py regular_tasks'
             ' > /dev/null')


def test_unused_keywords_are_removed(db, django_user_model):
    """A keyword no record uses is deleted, one still in use stays."""
    user = django_user_model.objects.create(username='some_editor')
    used = Tag.objects.create(name='Used Keyword')
    Tag.objects.create(name='Unused Keyword')
    TaggedItem.objects.create(
        tag=used, object_id=user.pk,
        content_type=ContentType.objects.get_for_model(user))
    out = StringIO()

    call_command('regular_tasks', stdout=out)

    assert Tag.objects.filter(name='Used Keyword').exists()
    assert not Tag.objects.filter(name='Unused Keyword').exists()
    lines = out.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith('remove_orphaned_tags: ')


def test_failed_task_does_not_stop_the_next(monkeypatch):
    """The next task still runs and the command ends with an error."""
    ran = []

    def broken():
        """Fail like a task whose database is not reachable."""
        raise ValueError('no connection')

    def fine():
        """Succeed and note that it ran."""
        ran.append('fine')
        return 'nothing to do'

    monkeypatch.setattr(TASKS, (('broken', broken), ('fine', fine)))
    out, err = StringIO(), StringIO()

    with pytest.raises(CommandError, match='broken'):
        call_command('regular_tasks', stdout=out, stderr=err)

    assert ran == ['fine']
    assert out.getvalue().splitlines() == ['fine: nothing to do']
    assert err.getvalue().splitlines() == [
        'broken: failed: ValueError: no connection']


def test_one_line_per_task(monkeypatch):
    """Each task that succeeds writes one line, in the order of TASKS."""
    monkeypatch.setattr(TASKS, (('first', lambda: '1 removed'),
                                ('second', lambda: '0 removed')))
    out = StringIO()

    call_command('regular_tasks', stdout=out)

    assert out.getvalue().splitlines() == [
        'first: 1 removed', 'second: 0 removed']


@pytest.mark.parametrize('columns', ['80', '120'])
def test_help_keeps_the_cron_line_whole(monkeypatch, columns):
    """The help shows the cron line on one line, ready to copy."""
    monkeypatch.setenv('COLUMNS', columns)
    command = load_command_class('apps.gcd', 'regular_tasks')
    parser = command.create_parser('manage.py', 'regular_tasks')

    assert CRON_LINE in parser.format_help().splitlines()
