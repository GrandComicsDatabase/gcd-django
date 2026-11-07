"""Formal procedure of gcd-policy and gcd-board topics, as the GCD wiki defines it.

Votes stay in apps.voting (agendas, ballots, quorum, secret ballots and ranked
choice); the forum links a topic to its agenda item and ballot and shows their
state. The forum adds the consensus step of the Policy Procedures: after three
days of discussion a coordinator seeks consensus; with no dissent in one week
and one day the item passes by consensus, and any dissent moves it to a vote.
"""
from datetime import timedelta
from urllib.parse import urlsplit

from django.urls import Resolver404, resolve
from django.utils import timezone

from .utils import to_id

DISCUSSION_BEFORE_CONSENSUS = timedelta(days=3)
CONSENSUS_WINDOW = timedelta(days=8)


def _voting():
    """The apps.voting models module, imported when called instead of when this module loads."""
    from apps.voting import models

    return models


def agendas_for(category):
    """Agendas whose mailing list is this group (gcd-policy@… for gcd-policy)."""
    models = _voting()
    return models.Agenda.objects.filter(
        agenda_mailing_lists__mailing_list__address__istartswith=f"{category.slug}@").distinct()


def agenda_items_for(category):
    """Pending and open items of the group's agendas."""
    models = _voting()
    return (models.AgendaItem.objects.exclude(state=False).filter(agenda__in=agendas_for(category))
            .select_related("agenda").order_by("-state", "created"))


def open_ballots_for(category):
    """Open ballots of the group's agendas, the nearest deadline first."""
    models = _voting()
    agendas = agendas_for(category)
    return models.Topic.objects.filter(open=True, agenda__in=agendas).select_related("agenda").order_by("deadline")


def parse_ballot(text):
    """A ballot from its number or the link of its page (/voting/ballot/<id>/)."""
    models = _voting()
    text = (text or "").strip()
    if to_id(text.lstrip("#")) is not None:
        return models.Topic.objects.filter(pk=to_id(text.lstrip("#"))).first()
    path = urlsplit(text).path
    try:
        match = resolve(path if path.endswith("/") else path + "/")
    except Resolver404:
        return None
    if match.url_name != "ballot":
        return None
    return models.Topic.objects.filter(pk=match.kwargs["id"]).first()


def ballot_state(ballot):
    """What a reader needs to know about a ballot: deadline, quorum progress, result."""
    voters = ballot.num_voters()
    quorum = ballot.agenda.quorum or 1
    return {
        "ballot": ballot,
        "voters": voters,
        "quorum": quorum,
        "quorum_reached": voters >= quorum,
        "results": list(ballot.results()) if ballot.result_calculated else [],
    }


def consensus_state(discussion, now=None):
    """None, or the state of the consensus step: waiting, impasse, ready or passed."""
    now = now or timezone.now()
    if discussion.consensus_passed_at:
        return {"state": "passed", "at": discussion.consensus_passed_at}
    if discussion.consensus_sought_at is None:
        return None
    # Removing an objection's post withdraws it.
    objections = list(discussion.objections.filter(post__is_deleted=False).select_related("user__indexer", "post"))
    ends = discussion.consensus_sought_at + CONSENSUS_WINDOW
    if objections:
        return {"state": "impasse", "objections": objections, "ends": ends}
    return {"state": "ready" if now >= ends else "waiting", "ends": ends}


def can_seek_consensus(discussion, now=None):
    """Whether consensus can be sought now: once per topic, after three days of discussion."""
    now = now or timezone.now()
    return (discussion.consensus_sought_at is None and discussion.consensus_passed_at is None
            and now - discussion.created_at >= DISCUSSION_BEFORE_CONSENSUS)
