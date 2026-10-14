"""One access policy for feeds, forms and direct content endpoints."""
from datetime import timedelta
from functools import wraps

from django.conf import settings

from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone

from .models import Category, Discussion, Post, Suspension
from .audit import request_audit
from .utils import get_client_ip


def _signed_in(user):
    """Whether there is a signed-in user with an active account; inactive accounts count as visitors."""
    return user is not None and user.is_authenticated and user.is_active


SIGNED_OUT = "You are signed out: sign in again, then repeat what you were doing."


def register_required(request):
    """The invitation to sign in or register, shown to visitors instead of the forum; a request from htmx
    (a button or a check made by the page) gets a line of text the page shows instead."""
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(SIGNED_OUT, status=403, content_type="text/plain; charset=utf-8")
        response["Cache-Control"] = "private, no-store"
        return response
    response = render(request, "forum/register_required.html", status=403)
    response["Cache-Control"] = "private, no-store"
    return response


def forum_view(view, public=False, always=False):
    """Gate a forum view: public views also serve visitors when a group is open to the public
    (none is by default); views marked always, such as unsubscribing, serve everyone."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        """Turn away visitors the view does not serve; for users, attribute content revisions to them and
        their IP during the view, and keep the response out of caches."""
        if not _signed_in(request.user):
            if always or (public and readable_categories(request.user).exists()):
                return view(request, *args, **kwargs)
            return register_required(request)
        token = request_audit.set((request.user.pk, get_client_ip(request)))
        try:
            response = view(request, *args, **kwargs)
        finally:
            request_audit.reset(token)
        # A view that set its own caching (an attachment, which never changes) keeps it.
        response.headers.setdefault("Cache-Control", "private, no-store")
        return response
    return wrapped


def _categories(user, field):
    """Active groups that field, read_access or post_access, opens to the user: public groups for visitors
    (reading only), every group for staff, else groups open to all users or that the user is a member of."""
    queryset = Category.objects.filter(is_active=True)
    if not _signed_in(user):
        if field == "read_access":
            return queryset.filter(read_access=Category.Access.PUBLIC)
        return Category.objects.none()
    if not (user.is_staff or user.is_superuser):
        open_to_users = (Category.Access.PUBLIC, Category.Access.USERS)
        queryset = queryset.filter(Q(**{f"{field}__in": open_to_users}) | Q(members=user))
    return queryset.distinct()


def readable_categories(user):
    """Active groups whose topics the user can read; visitors read only the public ones."""
    return _categories(user, "read_access")


def postable_categories(user):
    """Active groups the user can post in, except where suspended; none under a forum-wide suspension."""
    queryset = _categories(user, "post_access")
    suspensions = Suspension.objects.active().filter(user=user) if queryset.exists() else None
    if suspensions is not None and suspensions.exists():
        if suspensions.filter(category=None).exists():
            return Category.objects.none()
        queryset = queryset.exclude(pk__in=suspensions.values("category"))
    return queryset


def visible_categories(user):
    """Groups listed to the user: readable, or open to their topics."""
    return (readable_categories(user) | postable_categories(user)).distinct()


def accessible_discussions(user):
    """Topics in readable groups, plus the user's own topics in write-only groups."""
    if not _signed_in(user):
        return Discussion.objects.filter(category__in=readable_categories(user))
    return Discussion.objects.filter(
        Q(category__in=readable_categories(user))
        | Q(author=user, category__in=postable_categories(user))
    )


def readers(discussion, user_ids):
    """The ids, among user_ids, of the active users accessible_discussions lets read the topic, in a few
    queries whatever their number: readers of its group (any user, or members and staff), plus its author
    in a group they may post in but not read."""
    from django.contrib.auth import get_user_model

    category = discussion.category
    users = get_user_model().objects.filter(pk__in=list(user_ids), is_active=True)
    if not category.is_active or not Discussion.objects.filter(pk=discussion.pk).exists():
        return set()
    if category.read_access in (Category.Access.PUBLIC, Category.Access.USERS):
        found = set(users.values_list("pk", flat=True))
    else:
        found = set(users.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(forum_groups=category))
                    .values_list("pk", flat=True))
    author = users.filter(pk=discussion.author_id).first()
    if author is not None and author.pk not in found and category in postable_categories(author):
        found.add(author.pk)
    return found


def accessible_posts(user):
    """Published posts of the topics accessible_discussions opens to the user."""
    return Post.objects.filter(discussion__in=accessible_discussions(user))


# Daily limits by trust level, earned with approved changes to the GCD database (see
# database.trust_level): (setting, default) for accounts without approved changes, then for
# indexers. New accounts start 3 topics a day, as "max topics in first day" in Discourse.
POSTING_LIMITS = {
    0: {"topics": ("FORUM_NEW_MAX_TOPICS_PER_DAY", 3), "posts": ("FORUM_NEW_MAX_POSTS_PER_DAY", 20)},
    1: {"topics": ("FORUM_MAX_TOPICS_PER_DAY", 20), "posts": ("FORUM_MAX_POSTS_PER_DAY", 100)},
}


def posting_limit(user, new_topic=False):
    """Return why the user cannot post now, or None.

    Removed posts still count, so deleting does not reset the limit. Veterans, editors and staff have no
    limit. Posts sent at the same moment are counted without each other, so they can pass the limit by
    as many as are sent together: a lock on the user's row would deadlock with the notifications and
    emails other posts insert for that user, since each insert takes a shared lock on its user's row.
    """
    from .database import trust_level

    level = trust_level(user)
    if level >= 2:
        return None
    limits = {kind: getattr(settings, name, default) for kind, (name, default) in POSTING_LIMITS[level].items()}
    since = timezone.now() - timedelta(days=1)
    if new_topic and Discussion.all_objects.filter(author=user, created_at__gte=since).count() >= limits["topics"]:
        return f"You can start at most {limits['topics']} topics in 24 hours{_level_hint(level)}."
    if Post.all_objects.filter(author=user, created_at__gte=since).count() >= limits["posts"]:
        return f"You can post at most {limits['posts']} messages in 24 hours{_level_hint(level)}."
    return None


# Edits a day by trust level, as POSTING_LIMITS: each keeps both versions of the text in its revision.
EDIT_LIMITS = {0: ("FORUM_NEW_MAX_EDITS_PER_DAY", 30), 1: ("FORUM_MAX_EDITS_PER_DAY", 200)}


def edit_limit(user):
    """Why the user cannot edit now, or None: edits of the last 24 hours are counted by their revisions,
    by trust level (veterans, editors and staff have no limit)."""
    from .database import trust_level
    from .models import ContentRevision

    level = trust_level(user)
    if level >= 2:
        return None
    name, default = EDIT_LIMITS[level]
    limit = getattr(settings, name, default)
    since = timezone.now() - timedelta(days=1)
    if ContentRevision.objects.filter(actor=user, created_at__gte=since).exclude(before={}).count() >= limit:
        return f"You can make at most {limit} edits in 24 hours{_level_hint(level)}."
    return None


def _level_hint(level):
    """The end of the limit message for new accounts (level 0), on how the limit grows; empty otherwise."""
    return "; the limit grows with your first approved change to the database" if level == 0 else ""


def moderated_categories(user):
    """Groups whose reports the user handles: all for staff, else the groups they moderate."""
    if not _signed_in(user):
        return Category.objects.none()
    if user.is_staff or user.is_superuser:
        return Category.objects.all()
    return Category.objects.filter(moderators=user)


def needs_review(user, category):
    """Whether the post waits for a moderator: the first post of an account without approved
    changes to the database, like "approve post count" in Discourse. Members with earlier posts,
    also imported from the list archives, and the group's moderators post directly."""
    from .database import trust_level

    if not getattr(settings, "FORUM_REVIEW_FIRST_POSTS", True) or category.is_moderator(user):
        return False
    return trust_level(user) == 0 and not Post.objects.filter(author=user).exists()


def notify_review(post):
    """Tell the group's moderators, or staff when the group has none, about a post to review."""
    from django.contrib.auth import get_user_model

    from .models import Notification

    moderators = list(post.discussion.category.moderators.filter(is_active=True))
    if not moderators:
        moderators = list(get_user_model().objects.filter(is_staff=True, is_active=True))
    Notification.objects.bulk_create(
        [Notification(user=user, post=post, kind=Notification.Kind.REVIEW) for user in moderators],
        ignore_conflicts=True)
