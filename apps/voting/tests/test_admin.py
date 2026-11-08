import pytest
from django.contrib.auth.models import Permission

from apps.voting.models import Agenda, AgendaItem


@pytest.mark.parametrize('start, value, expected', [
    (True, '', None), (None, 'True', True), (True, 'False', False)],
    ids=['to_pending', 'to_open', 'to_closed'])
def test_agenda_item_state_can_be_changed_in_admin(admin_client, start,
                                                   value, expected):
    agenda = Agenda.objects.create(
      name='Test Agenda',
      permission=Permission.objects.get(codename='can_vote'))
    item = AgendaItem.objects.create(name='Item', agenda=agenda, state=start)

    response = admin_client.post(
      '/admin/voting/agendaitem/%d/change/' % item.id,
      {'name': item.name, 'agenda': agenda.id, 'notes': '', 'owner': '',
       'state': value, '_save': 'Save'})

    assert response.status_code == 302
    item.refresh_from_db()
    assert item.state is expected
