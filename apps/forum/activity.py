"""Topic subscriptions, read marks and notifications."""
from django.db.models import Count, Max, Min, OuterRef, Q, Subquery
from django.utils import timezone

from .models import Notification, TopicRead, TopicSubscription


def follow(user, discussion):
    """Subscribe the user to the topic, once, so later posts by others notify and email them."""
    TopicSubscription.objects.get_or_create(user=user, discussion=discussion)


def notify_followers(post):
    """Notify the followers of the topic who can still read it, except the author."""
    from .access import readers

    followers = set(TopicSubscription.objects.filter(discussion_id=post.discussion_id)
                    .exclude(user_id=post.author_id).values_list("user_id", flat=True))
    Notification.objects.bulk_create([
        Notification(user_id=user_id, post=post) for user_id in readers(post.discussion, followers)
    ], ignore_conflicts=True)


def link_records(post):
    """Link the topic to the GCD records whose pages the post links to; return the new links."""
    from .forms import save_records
    from .records import records_in_text

    return save_records(post.discussion, records_in_text(post.content), post.author)


def record_followers(post, links):
    """Users who follow one of the newly linked records and can read the topic, except the author."""
    from django.db.models import Q

    from .access import readers
    from .models import RecordSubscription

    if not links:
        return []
    match = Q()
    for link in links:
        match |= Q(content_type_id=link.content_type_id, object_id=link.object_id)
    subscriptions = (RecordSubscription.objects.filter(match).exclude(user_id=post.author_id)
                     .select_related("user"))
    users = {subscription.user for subscription in subscriptions}
    allowed = readers(post.discussion, {user.pk for user in users})
    return [user for user in users if user.pk in allowed]


def notify_record_followers(post, links):
    """Notify the followers of the newly linked records about the post; return them, to email them too."""
    users = record_followers(post, links)
    Notification.objects.bulk_create(
        [Notification(user=user, post=post, kind=Notification.Kind.RECORD) for user in users],
        ignore_conflicts=True)
    return users


def publish(post, new_links=()):
    """Everything that follows a new post: follow, notifications, records and emails."""
    from .mail import queue_post

    follow(post.author, post.discussion)
    notify_followers(post)
    links = list(new_links) + link_records(post)
    queue_post(post, extra_users=notify_record_followers(post, links))


def check_fix(discussion):
    """Mark the topic solved when a linked database change is approved, once, and tell its followers."""
    from .database import is_approved
    from .models import Discussion, DiscussionChange

    if discussion.fixed_by_id:
        return False
    for link in DiscussionChange.objects.filter(discussion=discussion).select_related("changeset"):
        if is_approved(link.changeset):
            break
    else:
        return False
    updates = {"fixed_by": link.changeset}
    if discussion.status == Discussion.Status.OPEN:
        updates["status"] = Discussion.Status.RESOLVED
    if not Discussion.all_objects.filter(pk=discussion.pk, fixed_by=None).update(**updates):
        return False
    for field, value in updates.items():
        setattr(discussion, field, value)
    first = discussion.posts.order_by("pk").first()
    if first is not None:
        followers = TopicSubscription.objects.filter(discussion=discussion).values_list("user_id", flat=True)
        Notification.objects.bulk_create(
            [Notification(user_id=user_id, post=first, kind=Notification.Kind.FIXED) for user_id in followers],
            ignore_conflicts=True)
    return True


def check_all_fixes():
    """Run from cron: topics whose linked changes were approved since the last run."""
    from .models import Discussion

    return sum(check_fix(discussion) for discussion in
               Discussion.objects.filter(fixed_by=None, changes__isnull=False).distinct())


def mark_read(user, discussion):
    """Record the visit; return the last post id the user had seen, or None."""
    latest = discussion.posts.aggregate(latest=Max("pk"))["latest"] or 0
    read, created = TopicRead.objects.get_or_create(
        user=user, discussion=discussion, defaults={"last_read_post_id": latest})
    previous = None if created else read.last_read_post_id
    if not created and latest > previous:
        TopicRead.objects.filter(pk=read.pk).update(last_read_post_id=latest)
    # A review request is done on the Moderation page, where the held post is shown, not by opening the topic.
    Notification.objects.filter(user=user, post__discussion=discussion, read_at=None).exclude(
        kind=Notification.Kind.REVIEW).update(read_at=timezone.now())
    return previous


def with_unread(queryset, user):
    """Annotate topics with the posts by others since the user's last visit."""
    last_read = TopicRead.objects.filter(user=user, discussion=OuterRef("pk")).values("last_read_post_id")
    queryset = queryset.annotate(last_read_post_id=Subquery(last_read[:1]))
    newer = Q(posts__is_deleted=False, posts__awaiting_review=False,
              posts__pk__gt=Subquery(last_read[:1])) & ~Q(posts__author=user)
    return queryset.annotate(
        unread_count=Count("posts", filter=newer, distinct=True),
        first_unread_id=Min("posts__pk", filter=newer),
    )


def visible_notifications(user):
    """The user's notifications the notifications page lists: those of topics the user can still read
    (not removed, not moved out of reach), and the review requests of moderators."""
    from .access import accessible_discussions

    return Notification.objects.filter(
        Q(post__discussion__in=accessible_discussions(user)) | Q(kind=Notification.Kind.REVIEW), user=user)


def unread_notifications(user):
    """The visible notifications with no read_at, counted in the sidebar and marked by "Mark all as read";
    one of a topic the user can no longer open would keep the badge up for good."""
    return visible_notifications(user).filter(read_at=None)
