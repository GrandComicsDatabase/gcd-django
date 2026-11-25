import pytest

from django.core.management import call_command

from apps.gcd.models import Character, Group, GroupMembership
from apps.gcd.models.character import GroupMembershipType
from apps.oi.forms.character import GroupMembershipRevisionForm


@pytest.fixture
def membership(db):
    # The seeded character appears in a story as a member of the group.
    call_command('seed_development_data', verbosity=0)
    membership_type, _ = GroupMembershipType.objects.get_or_create(
      type='member', defaults={'reverse_type': 'members'})
    return GroupMembership.objects.create(
      character=Character.objects.get(name='[GCD DEV] Captain Example'),
      group=Group.objects.get(name='[GCD DEV] Example League'),
      membership_type=membership_type, year_joined=1990, notes='')


@pytest.mark.parametrize('year_joined, valid', [(1990, False), (2000, True)])
def test_membership_form_refuses_identical_membership(membership,
                                                      year_joined, valid):
    form = GroupMembershipRevisionForm(data={
      'character': membership.character.id,
      'group': membership.group.id,
      'membership_type': membership.membership_type.id,
      'year_joined': year_joined,
      'notes': '',
      'comments': ''})

    assert form.is_valid() is valid


def test_duplicate_membership_with_appearances_is_deletable(membership):
    assert not membership.deletable()

    duplicate = GroupMembership.objects.get(pk=membership.pk)
    duplicate.pk = None
    duplicate.save()

    assert duplicate.deletable()
    assert membership.deletable()
