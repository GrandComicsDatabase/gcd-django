"""What the forum reads from the GCD database work: changes, experts and trust.

The forum never writes these data. Changes (changesets) come from apps.oi:
each record type has a revision class, such as SeriesRevision, with a foreign
key named like the record type and one to its changeset.
"""
from collections import Counter
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.urls import Resolver404, resolve

from .records import RECORD_TYPES
from .utils import to_id

EXPERTS = 5
# Approved changes that make a user's posting limits lighter, or lift them.
TRUSTED_CHANGES = 1
VETERAN_CHANGES = 100


def _oi():
    """The models and states modules of apps.oi, imported when called instead of when this module loads."""
    from apps.oi import models, states

    return models, states


def revision_class(key):
    """The apps.oi revision model of a record type key, such as SeriesRevision; None when there is none."""
    models, _ = _oi()
    name = RECORD_TYPES.get(key)
    return getattr(models, f"{name}Revision", None) if name else None


def changeset_state(changeset):
    """The display name of the changeset's state, such as "Under Review"; "Unknown" for any other state."""
    _, states = _oi()
    return states.DISPLAY_NAME.get(changeset.state, "Unknown")


def is_approved(changeset):
    """Whether the changeset's state is APPROVED, so its changes are in the database."""
    _, states = _oi()
    return changeset.state == states.APPROVED


def parse_changeset(text):
    """A changeset from its number or the link of one of its pages (/changeset/<id>/...)."""
    models, _ = _oi()
    text = (text or "").strip()
    if to_id(text.lstrip("#")) is not None:
        number = to_id(text.lstrip("#"))
    else:
        path = urlsplit(text).path
        try:
            match = resolve(path if path.endswith("/") else path + "/")
        except Resolver404:
            return None
        number = match.kwargs.get("id") if "changeset/" in path else None
    return models.Changeset.objects.filter(pk=number).select_related("indexer").first() if number else None


def changes_for_records(links, since=None):
    """Changesets that touch the linked records, newest first."""
    models, _ = _oi()
    ids = set()
    for link in links:
        key = _key(link)
        revisions = revision_class(key)
        if revisions is None:
            continue
        queryset = revisions.objects.filter(**{f"{key}_id": link.object_id})
        if since is not None:
            queryset = queryset.filter(changeset__created__gte=since)
        ids.update(queryset.values_list("changeset_id", flat=True)[:50])
    return list(models.Changeset.objects.filter(pk__in=ids).select_related("indexer__indexer")
                .order_by("-created")[:20])


def record_experts(links, exclude=(), limit=EXPERTS):
    """Active users with the most approved changes to the linked records; for a series, its issues too."""
    models, states = _oi()
    counts = Counter()
    for link in links:
        key = _key(link)
        revisions = revision_class(key)
        if revisions is None:
            continue
        querysets = [revisions.objects.filter(**{f"{key}_id": link.object_id})]
        if key == "series":
            querysets.append(models.IssueRevision.objects.filter(issue__series_id=link.object_id))
        for queryset in querysets:
            for row in (queryset.filter(changeset__state=states.APPROVED).values("changeset__indexer")
                        .annotate(changes=Count("changeset", distinct=True))):
                counts[row["changeset__indexer"]] += row["changes"]
    for user_id in exclude:
        counts.pop(user_id, None)
    users = get_user_model().objects.select_related("indexer").in_bulk(
        [user_id for user_id, _ in counts.most_common(limit * 2)])
    return [{"user": users[user_id], "changes": changes} for user_id, changes in counts.most_common()
            if user_id in users and users[user_id].is_active][:limit]


def approved_changes(user):
    """How many of the user's changesets are approved, the count trust_level grades accounts by."""
    models, states = _oi()
    return models.Changeset.objects.filter(indexer=user, state=states.APPROVED).count()


def trust_level(user):
    """0 for accounts without approved changes, 1 for indexers, 2 for veterans, editors, staff and
    the moderators (list coordinators) of a group."""
    if (user.is_staff or user.is_superuser or user.groups.filter(name="editor").exists()
            or user.forum_moderated_groups.exists()):
        return 2
    changes = approved_changes(user)
    return 2 if changes >= VETERAN_CHANGES else 1 if changes >= TRUSTED_CHANGES else 0


def touches_records(changeset, links):
    """Whether the changeset revises one of the linked records (a series also through its issues)."""
    models, _ = _oi()
    for link in links:
        key = _key(link)
        revisions = revision_class(key)
        if revisions is not None and revisions.objects.filter(
                changeset=changeset, **{f"{key}_id": link.object_id}).exists():
            return True
        if key == "series" and models.IssueRevision.objects.filter(
                changeset=changeset, issue__series_id=link.object_id).exists():
            return True
    return False


def _key(link):
    """The record type key of a topic's link to a record (DiscussionRecord); None for other types."""
    from .records import record_key

    return record_key(link.content_type)
