"""Topic subscriptions, read marks and notifications."""
from django.db.models import Count, Max, Min, OuterRef, Q, Subquery
from django.utils import timezone

from .models import Notification, TopicRead, TopicSubscription


def follow(user, discussion):
    TopicSubscription.objects.get_or_create(user=user, discussion=discussion)


def notify_followers(post):
    """Notify the followers of the topic who can still read it, except the author."""
    from .access import accessible_discussions

    followers = (TopicSubscription.objects.filter(discussion_id=post.discussion_id)
                 .exclude(user_id=post.author_id).select_related("user"))
    Notification.objects.bulk_create([
        Notification(user=subscription.user, post=post) for subscription in followers
        if accessible_discussions(subscription.user).filter(pk=post.discussion_id).exists()
    ], ignore_conflicts=True)


def mark_read(user, discussion):
    """Record the visit; return the last post id the user had seen, or None."""
    latest = discussion.posts.aggregate(latest=Max("pk"))["latest"] or 0
    read, created = TopicRead.objects.get_or_create(
        user=user, discussion=discussion, defaults={"last_read_post_id": latest})
    previous = None if created else read.last_read_post_id
    if not created and latest > previous:
        TopicRead.objects.filter(pk=read.pk).update(last_read_post_id=latest)
    Notification.objects.filter(user=user, post__discussion=discussion, read_at=None).update(
        read_at=timezone.now())
    return previous


def with_unread(queryset, user):
    """Annotate topics with the posts by others since the user's last visit."""
    last_read = TopicRead.objects.filter(user=user, discussion=OuterRef("pk")).values("last_read_post_id")
    queryset = queryset.annotate(last_read_post_id=Subquery(last_read[:1]))
    newer = Q(posts__is_deleted=False, posts__pk__gt=Subquery(last_read[:1])) & ~Q(posts__author=user)
    return queryset.annotate(
        unread_count=Count("posts", filter=newer, distinct=True),
        first_unread_id=Min("posts__pk", filter=newer),
    )


def unread_notifications(user):
    return Notification.objects.filter(user=user, read_at=None)
