import logging

logger = logging.getLogger(__name__)


def to_id(value):
    """A database id typed or sent by a user: ASCII digits that fit the id columns, else None."""
    value = str(value if value is not None else "").strip()
    return int(value) if value.isascii() and value.isdigit() and len(value) <= 18 else None


def display_name(user):
    """How the forum names a person, as the rest of GCD does: the indexer's first and last name (Indexer's
    str). Never the username, which GCD builds from the email address. An account without an indexer
    profile or a name shows as "GCD user <id>"."""
    indexer = getattr(user, "indexer", None)
    return (str(indexer).strip() if indexer is not None else "") or f"GCD user {user.pk}"


def get_client_ip(request):
    """Return the peer IP (REMOTE_ADDR). With FORUM_TRUST_X_FORWARDED_FOR set to the number of proxies in
    front of the site (True counts as one), the address is the X-Forwarded-For entry the farthest of them
    added, counted from the right: the entries left of it come from the client, who can write anything."""
    from django.conf import settings

    from ipaddress import ip_address

    candidate = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    proxies = int(getattr(settings, "FORUM_TRUST_X_FORWARDED_FOR", 0) or 0)
    if proxies:
        entries = [entry.strip() for entry in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if entry.strip()]
        if len(entries) >= proxies:
            candidate = entries[-proxies]
    try:
        return str(ip_address(candidate))
    except ValueError:
        logger.warning("Unreadable client address %r: stored as 0.0.0.0", candidate[:100])
        return "0.0.0.0"


def can_edit(user, content):
    """Whether the user may edit or move the content: a moderator of its group (or staff), or its author
    while they may post in the group, so a suspended author cannot rewrite or move what they posted."""
    category = getattr(content, "discussion", content).category
    return user.is_authenticated and (
        category.is_moderator(user) or (content.author_id == user.pk and category.can_post(user)))


def can_moderate(user, content):
    """Author, staff or a moderator of the group may remove content; editing and moving also need
    can_edit."""
    discussion = getattr(content, "discussion", content)
    return user.is_authenticated and (
        content.author_id == user.pk or discussion.category.is_moderator(user))
