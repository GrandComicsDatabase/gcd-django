from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string

from apps.oi import states


class ChangesetList(list):
    def count(self):
        return len(self)


def render_queue(changeset_state, queue_name='reviews'):
    changeset = SimpleNamespace(
        id=123,
        state=changeset_state,
        display_state=states.DISPLAY_NAME[changeset_state],
        country=None,
        queue_name='Northstar Comics #12',
        changeset_action='',
        queue_descriptor='',
        indexer=SimpleNamespace(indexer=None),
        approver=SimpleNamespace(indexer=None),
        modified=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    context = {
        'actions': 'oi/bits/approval_actions.html',
        'countries': {},
        'country_names': {},
        'data': [{
            'object_name': 'Issues',
            'changesets': ChangesetList([changeset]),
        }],
        'link_target': 'preview',
        'perms': SimpleNamespace(
            indexer=SimpleNamespace(can_approve=False)),
        'queue_name': queue_name,
        'states': states,
        'user': SimpleNamespace(
            indexer=SimpleNamespace(collapse_compare_view=False)),
    }
    return render_to_string('oi/bits/standard_queues.html', context)


@pytest.mark.parametrize(
    ('changeset_state', 'label', 'classes'),
    (
        (states.OPEN, 'E', 'bg-red-400'),
        (states.DISCUSSED, 'D',
         'bg-yellow-400'),
        (states.REVIEWING, 'R', 'bg-green-400'),
    ),
)
def test_reviewing_queue_shows_mobile_state_badge(
        changeset_state, label, classes):
    rendered = render_queue(changeset_state)

    assert label in rendered
    assert 'sm:hidden block text-center' in rendered
    assert classes in rendered


def test_mobile_state_badge_is_limited_to_reviewing_queue():
    rendered = render_queue(states.REVIEWING, queue_name='pending')

    assert 'bg-green-400">R' not in rendered
    assert 'sm:hidden block text-center' not in rendered
