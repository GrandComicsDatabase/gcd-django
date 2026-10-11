"""One access policy for feeds, forms and direct content endpoints."""
from datetime import timedelta
from functools import wraps

from django.conf import settings

from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone

from .models import Category, Discussion, Post, Suspension
from .audit import request_audit
from .utils import get_client_ip


def _signed_in(user):
    return user is not None and user.is_authenticated and user.is_active


def forum_view(view, public=False):
    """Gate a forum view: public views also serve visitors without an account."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not _signed_in(request.user):
            if public:
                return view(request, *args, **kwargs)
            response = render(request, "forum/register_required.html", status=403)
            response["Cache-Control"] = "private, no-store"
            return response
        token = request_audit.set((request.user.pk, get_client_ip(request)))
        try:
            response = view(request, *args, **kwargs)
        finally:
            request_audit.reset(token)
        response["Cache-Control"] = "private, no-store"
        return response
    return wrapped


def _categories(user, field):
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
    return _categories(user, "read_access")


def postable_categories(user):
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


def accessible_posts(user):
    return Post.objects.filter(discussion__in=accessible_discussions(user))


def posting_limit(user, new_topic=False):
    """Return why the user cannot post now, or None; staff have no limit.

    Removed posts still count, so deleting does not reset the limit.
    """
    if user.is_staff or user.is_superuser:
        return None
    since = timezone.now() - timedelta(days=1)
    if new_topic:
        limit = getattr(settings, "FORUM_MAX_TOPICS_PER_DAY", 20)
        if Discussion.all_objects.filter(author=user, created_at__gte=since).count() >= limit:
            return f"You can start at most {limit} topics in 24 hours."
    limit = getattr(settings, "FORUM_MAX_POSTS_PER_DAY", 100)
    if Post.all_objects.filter(author=user, created_at__gte=since).count() >= limit:
        return f"You can post at most {limit} messages in 24 hours."
    return None
