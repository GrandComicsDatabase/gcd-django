def get_client_ip(request):
    """Return the peer IP; trust proxy headers only when explicitly configured."""
    from django.conf import settings

    from ipaddress import ip_address

    candidate = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    if getattr(settings, "FORUM_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return "0.0.0.0"


def can_moderate(user, content):
    """Author, staff or a moderator of the group may edit, move and remove content."""
    discussion = getattr(content, "discussion", content)
    return user.is_authenticated and (
        content.author_id == user.pk or discussion.category.is_moderator(user))
