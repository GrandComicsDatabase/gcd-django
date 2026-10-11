from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from markdownx.models import MarkdownxField


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        with transaction.atomic(using=self.db):
            objects = list(self)
            for obj in objects:
                obj.delete()
        return len(objects), {self.model._meta.label: len(objects)}

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AuditedContent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_updated",
    )
    ip_address = models.GenericIPAddressField()
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from .audit import request_audit, snapshot
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            previous = type(self).all_objects.using(using).select_for_update().filter(pk=self.pk).first() if self.pk else None
            result = super().save(*args, **kwargs)
            current = type(self).all_objects.using(using).get(pk=self.pk)
            before = snapshot(previous) if previous else {}
            after = snapshot(current)
            if before != after:
                actor, ip = request_audit.get() or (self.updated_by_id, None)
                ContentRevision.objects.using(using).create(
                    content_type=ContentType.objects.db_manager(using).get_for_model(self),
                    object_id=self.pk, actor_id=actor, ip_address=ip,
                    before=before, after=after,
                )
            return result

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))


class Category(models.Model):
    """A discussion group, one per GCD email list."""

    class Section(models.TextChoices):
        MAIN = "main", "Main lists"
        INTERNATIONAL = "international", "International lists"
        SPECIALIZED = "specialized", "Specialized lists"

    class Access(models.TextChoices):
        PUBLIC = "public", "Anyone, also without an account (reading only)"
        USERS = "users", "Any GCD user"
        MEMBERS = "members", "Group members"

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=16, choices=Section.choices, default=Section.MAIN)
    language = models.CharField(
        max_length=8, blank=True,
        help_text="Language code of the posts, for groups that write in one language.")
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)
    read_access = models.CharField(max_length=8, choices=Access.choices, default=Access.USERS)
    post_access = models.CharField(max_length=8, choices=Access.choices, default=Access.USERS)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="forum_groups")
    # Coordinators of the list: they pin, close, move and remove topics of the group.
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="forum_moderated_groups")

    class Meta:
        ordering = ("position", "name")
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("forum:group", kwargs={"slug": self.slug})

    def is_moderator(self, user):
        return user.is_authenticated and (
            user.is_staff or user.is_superuser or self.moderators.filter(pk=user.pk).exists())

    def _allows(self, user, access):
        if not (user.is_authenticated and user.is_active and self.is_active):
            return False
        return (access in (self.Access.PUBLIC, self.Access.USERS) or user.is_staff
                or user.is_superuser or self.members.filter(pk=user.pk).exists())

    def can_read(self, user):
        if self.read_access == self.Access.PUBLIC and self.is_active:
            return True
        return self._allows(user, self.read_access)

    def can_post(self, user):
        return self._allows(user, self.post_access) and not Suspension.objects.active().filter(
            Q(category=self) | Q(category=None), user=user).exists()


class Discussion(AuditedContent):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="forum_discussions",
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="discussions"
    )
    views_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    # The last move, so the origin group keeps a pointer to the topic.
    moved_from = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.PROTECT, related_name="moved_discussions"
    )
    moved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="forum_moved_discussions",
    )
    moved_at = models.DateTimeField(null=True, blank=True)
    # The reply that answers the question; setting it marks the topic resolved.
    answer = models.ForeignKey(
        "Post", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # A closed duplicate points to the topic that holds the discussion.
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates")
    # Kept up to date by Post.save, so topic lists need no aggregate over every post.
    post_count = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-is_pinned", "-created_at")
        indexes = [models.Index(fields=("-is_pinned", "-last_activity"), name="forum_topic_activity")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("forum:discussion-detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "discussion"
            if base in {"new", "groups", "notifications", "posts", "records", "report"}:
                base += "-discussion"
            slug = base
            counter = 2
            while Discussion.all_objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix = f"-{counter}"
                slug = f"{base[:220 - len(suffix)]}{suffix}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def update_counters(self):
        stats = Post.objects.filter(discussion_id=self.pk).aggregate(count=Count("pk"), last=Max("created_at"))
        self.post_count, self.last_activity = stats["count"], stats["last"]
        Discussion.all_objects.filter(pk=self.pk).update(
            post_count=self.post_count, last_activity=self.last_activity)


class DiscussionRecord(models.Model):
    """A GCD record (issue, series, character...) a discussion is about."""

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="records")
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="forum_record_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("discussion", "content_type", "object_id"), name="forum_unique_discussion_record"
            )
        ]
        indexes = [models.Index(fields=("content_type", "object_id"))]

    def __str__(self):
        return f"{self.content_type.model} {self.object_id}"


class Post(AuditedContent):
    discussion = models.ForeignKey(
        Discussion, on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="forum_posts",
    )
    content = MarkdownxField()
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Post #{self.pk} in {self.discussion}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.discussion.update_counters()


class TopicSubscription(models.Model):
    """A user follows a topic: replies notify them."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_subscriptions")
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "discussion"), name="forum_unique_subscription")
        ]


class TopicRead(models.Model):
    """The last post a user has seen in a topic; later posts are unread."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_reads")
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="reads")
    last_read_post_id = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "discussion"), name="forum_unique_read")
        ]


class Notification(models.Model):
    """A new post in a topic the user follows."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_notifications")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="notifications")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at"))]
        constraints = [
            models.UniqueConstraint(fields=("user", "post"), name="forum_unique_notification")
        ]


class GroupEmailSubscription(models.Model):
    """A user receives every post of a group by email, like a mailing list member."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_group_emails")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="email_subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "category"), name="forum_unique_group_email")
        ]


class OutgoingEmail(models.Model):
    """One post to email to one user; the forum_mail command sends the queue."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="outgoing_emails")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_outgoing_emails")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(fields=("post", "user"), name="forum_unique_outgoing_email")
        ]


class IncomingEmail(models.Model):
    """Every message read from the forum mailbox, accepted or not, once per Message-ID."""

    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        IGNORED = "ignored", "Ignored"

    message_id = models.CharField(max_length=255, unique=True)
    sender = models.CharField(max_length=255)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=255, blank=True)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)


class PostVote(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_post_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("post", "user"), name="forum_unique_post_vote"
            )
        ]


class Report(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        DISMISSED = "dismissed", "Dismissed"
        ACTIONED = "actioned", "Actioned"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="forum_reports",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="forum_reports_reviewed",
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("reporter", "content_type", "object_id"),
                name="forum_unique_report_per_content",
            )
        ]
        indexes = [models.Index(fields=("content_type", "object_id"))]

    def __str__(self):
        return f"Report #{self.pk} ({self.get_status_display()})"


class SuspensionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(Q(until=None) | Q(until__gt=timezone.now()))


class Suspension(models.Model):
    """Posting privileges revoked for a user, in one group or in every group."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_suspensions")
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.CASCADE, related_name="suspensions",
        help_text="Leave empty to suspend the user in every group.")
    reason = models.TextField()
    until = models.DateTimeField(null=True, blank=True, help_text="Leave empty for no end date.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="forum_suspensions_given")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SuspensionQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user} in {self.category or 'every group'}"


class ContentRevision(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        ordering = ("-created_at",)
