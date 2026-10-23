import uuid
from os.path import dirname, join, normpath, splitext

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from markdownx.models import MarkdownxField
from unidecode import unidecode

# Text written by people (and email headers) can hold any Unicode character, emoji included: these columns
# are utf8mb4 whatever the database default is, as upstream #746 did for change comments.
UTF8MB4 = "utf8mb4_unicode_ci"
# Forum URLs that a topic slug must not take.
RESERVED_SLUGS = {"new", "groups", "notifications", "posts", "records", "report", "feed", "preview",
                  "moderation", "email", "similar"}
# Inserts of a new topic tried before a slug conflict is let through.
SLUG_ATTEMPTS = 3


class SoftDeleteQuerySet(models.QuerySet):
    """Querysets of topics and posts: delete() marks the objects removed, hard_delete() drops the rows."""
    def delete(self):
        """Soft-delete each object through its own delete(), in one transaction, so every removal is
        audited; the counts come back in the form QuerySet.delete() uses."""
        with transaction.atomic(using=self.db):
            objects = list(self)
            for obj in objects:
                obj.delete()
        return len(objects), {self.model._meta.label: len(objects)}

    def hard_delete(self):
        """Delete the rows from the database with Django's own delete; no revision is recorded."""
        return super().delete()

    def alive(self):
        """The objects not removed, including those waiting for a moderator."""
        return self.filter(is_deleted=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Published content: neither removed nor waiting for a moderator."""

    def get_queryset(self):
        """Leave out removed content and content waiting for a moderator."""
        return super().get_queryset().filter(is_deleted=False, awaiting_review=False)


class AuditedContent(models.Model):
    """Base of topics and posts: who created and last changed them, the IP recorded when posted, their
    soft delete and review flags, and a ContentRevision for each save that changes audited fields."""
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
    # The first post of a new account waits for a moderator (access.needs_review).
    awaiting_review = models.BooleanField(default=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        """Abstract: no table of its own; Discussion and Post each get these fields."""
        abstract = True

    def save(self, *args, **kwargs):
        """Save, and record a ContentRevision when the content is created or its audited fields change.

        The revision holds the audited fields before and after. The actor and IP come from request_audit;
        when it is not set, the actor is updated_by and no IP is recorded. The old row is read with
        select_for_update, so concurrent saves of it run one after the other, each compared with the row
        the previous one left.
        """
        from .audit import request_audit, snapshot
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            previous = (type(self).all_objects.using(using).select_for_update().filter(pk=self.pk).first()
                        if self.pk else None)
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
        """Soft delete: mark the content removed but keep its row; the save records the change."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))

    def restore(self):
        """Undo a soft delete; the save records the change."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=("is_deleted", "deleted_at", "updated_at"))


class Category(models.Model):
    """A discussion group, one per GCD email list."""

    class Section(models.TextChoices):
        """The Email Lists FAQ section of a group; the forum lists the sections in this order."""
        MAIN = "main", "Main lists"
        INTERNATIONAL = "international", "International lists"
        SPECIALIZED = "specialized", "Specialized lists"

    class Access(models.TextChoices):
        """Levels of read_access and post_access; public lets visitors read, but posting needs an account."""
        PUBLIC = "public", "Anyone, also without an account (reading only)"
        USERS = "users", "Any GCD user"
        MEMBERS = "members", "Group members"

    name = models.CharField(max_length=100, unique=True, db_collation=UTF8MB4)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True, db_collation=UTF8MB4)
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
        """Order groups by position, then name; the plural is spelled "categories"."""
        ordering = ("position", "name")
        verbose_name_plural = "categories"

    def __str__(self):
        """The group's name."""
        return self.name

    def get_absolute_url(self):
        """The group's page, which lists its topics."""
        return reverse("forum:group", kwargs={"slug": self.slug})

    def is_moderator(self, user):
        """Whether the user moderates the group: staff, superusers and the group's moderators do."""
        return user.is_authenticated and (
            user.is_staff or user.is_superuser or self.moderators.filter(pk=user.pk).exists())

    def _allows(self, user, access):
        """Whether the user meets an access level of the group: signed in and active, the group active,
        and for members-only also a member, staff or superuser."""
        if not (user.is_authenticated and user.is_active and self.is_active):
            return False
        return (access in (self.Access.PUBLIC, self.Access.USERS) or user.is_staff
                or user.is_superuser or self.members.filter(pk=user.pk).exists())

    def can_read(self, user):
        """Whether the user may read the group; an active public group is open to visitors too."""
        if self.read_access == self.Access.PUBLIC and self.is_active:
            return True
        return self._allows(user, self.read_access)

    def can_post(self, user):
        """Whether the user may post here: post access allows it and no active suspension applies."""
        return self._allows(user, self.post_access) and not Suspension.objects.active().filter(
            Q(category=self) | Q(category=None), user=user).exists()


class Discussion(AuditedContent):
    """A topic in a group: its title, state and counters; its first post is the opening message."""
    class Status(models.TextChoices):
        """Open, resolved (shown as Solved), or archived; an archived topic takes no more replies."""
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200, db_collation=UTF8MB4)
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
    # The approved database change that fixed what the topic reported.
    fixed_by = models.ForeignKey(
        "oi.Changeset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Formal procedure of policy and board topics: the agenda item, its ballot and consensus.
    agenda_item = models.ForeignKey(
        "voting.AgendaItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ballot = models.ForeignKey(
        "voting.Topic", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    consensus_sought_at = models.DateTimeField(null=True, blank=True)
    consensus_sought_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    consensus_passed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Pinned first, then newest; an index on pinned and last activity serves the topic lists."""
        ordering = ("-is_pinned", "-created_at")
        indexes = [models.Index(fields=("-is_pinned", "-last_activity"), name="forum_topic_activity")]

    def __str__(self):
        """The topic's title."""
        return self.title

    def get_absolute_url(self):
        """The topic's page."""
        return reverse("forum:discussion-detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        """Fill an empty slug from the title, unique among all topics and never a reserved URL word.

        A topic created at the same moment can take the same slug between the check and the insert: the
        insert then fails on the unique index and is tried again with the next free slug.
        """
        if self.slug:
            return super().save(*args, **kwargs)
        using = kwargs.get("using") or self._state.db or "default"
        for attempt in range(SLUG_ATTEMPTS):
            self.slug = self.free_slug(using)
            try:
                with transaction.atomic(using=using):
                    return super().save(*args, **kwargs)
            except IntegrityError:
                taken = Discussion.all_objects.using(using).filter(slug=self.slug).exists()
                self.slug = ""
                if not taken or attempt == SLUG_ATTEMPTS - 1:
                    raise

    def free_slug(self, using="default"):
        """The title as a slug, with a number added when topics already have it. The title is spelled in
        ASCII first (Unidecode), so "Østlandet" gives "ostlandet" and a Greek or Japanese title keeps its
        words; a title with no letters or digits gives "discussion"."""
        base = slugify(unidecode(self.title))[:200] or "discussion"
        if base in RESERVED_SLUGS:
            base += "-discussion"
        taken = set(Discussion.all_objects.using(using).filter(slug__startswith=base).exclude(pk=self.pk)
                    .values_list("slug", flat=True))
        slug, counter = base, 2
        while slug in taken:
            suffix = f"-{counter}"
            slug = f"{base[:220 - len(suffix)]}{suffix}"
            counter += 1
        return slug

    def solved_status(self):
        """The status the topic's own marks give it: archived stays archived; an accepted answer, a fixing
        database change or a passed consensus make it resolved; else it is open."""
        if self.status == self.Status.ARCHIVED:
            return self.status
        if self.answer_id or self.fixed_by_id or self.consensus_passed_at:
            return self.Status.RESOLVED
        return self.Status.OPEN

    @classmethod
    def lock(cls, pk, using="default"):
        """Lock the topic's row until the transaction ends, so requests that change the topic run one after
        the other. Take it before inserting rows that refer to the topic: their foreign key check takes a
        shared lock on it, and asking for the exclusive lock after that deadlocks with a concurrent request
        that does the same (InnoDB)."""
        list(cls.all_objects.using(using).select_for_update().filter(pk=pk).values_list("pk", flat=True))

    def update_counters(self):
        """Store the published post count and newest post date with an update, which records no revision."""
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
        """In link order; a record is linked to a topic once; an index finds the topics about a record."""
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("discussion", "content_type", "object_id"), name="forum_unique_discussion_record"
            )
        ]
        indexes = [models.Index(fields=("content_type", "object_id"))]

    def __str__(self):
        """The record's model name and id, such as "issue 42"."""
        return f"{self.content_type.model} {self.object_id}"


class Post(AuditedContent):
    """A message in a topic, in Markdown; parent is the post it replies to."""
    discussion = models.ForeignKey(
        Discussion, on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="forum_posts",
    )
    content = MarkdownxField(db_collation=UTF8MB4)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    class Meta:
        """Oldest first, by creation date."""
        ordering = ("created_at",)

    def __str__(self):
        """The post's id and its topic's title."""
        return f"Post #{self.pk} in {self.discussion}"

    def get_absolute_url(self):
        """The topic page that holds the post, scrolled to the post."""
        # The post query finds the page of a long topic that holds the post.
        return f"{self.discussion.get_absolute_url()}?post={self.pk}#post-{self.pk}"

    def delete(self, using=None, keep_parents=False):
        """Soft delete; a removed post that was the topic's answer no longer solves it."""
        super().delete(using, keep_parents)
        topic = Discussion.all_objects.filter(pk=self.discussion_id, answer_id=self.pk).first()
        if topic is not None:
            topic.answer = None
            Discussion.all_objects.filter(pk=topic.pk, answer_id=self.pk).update(
                answer=None, status=topic.solved_status())

    def save(self, *args, **kwargs):
        """Save, then refresh the topic's post count and last activity; the topic is locked first (see
        Discussion.lock)."""
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            Discussion.lock(self.discussion_id, using)
            super().save(*args, **kwargs)
            self.discussion.update_counters()


class DiscussionChange(models.Model):
    """A change to the GCD database (changeset) that answers a topic, such as an error fix."""

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="changes")
    changeset = models.ForeignKey("oi.Changeset", on_delete=models.CASCADE, related_name="+")
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Latest changeset first; a changeset is linked to a topic once."""
        ordering = ("-changeset_id",)
        constraints = [
            models.UniqueConstraint(fields=("discussion", "changeset"), name="forum_unique_discussion_change")
        ]


class RecordSubscription(models.Model):
    """A user follows a GCD record: new topics about it notify them."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_record_subscriptions")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """An index finds the followers of a record; a user follows a record once."""
        indexes = [models.Index(fields=("content_type", "object_id"))]
        constraints = [
            models.UniqueConstraint(fields=("user", "content_type", "object_id"),
                                    name="forum_unique_record_subscription")
        ]


class Objection(models.Model):
    """Dissent while a coordinator seeks consensus; it moves the item to a vote."""

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="objections")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Oldest first; one objection per user and topic."""
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(fields=("discussion", "user"), name="forum_unique_objection")
        ]


class TopicSubscription(models.Model):
    """A user follows a topic: replies notify them."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_subscriptions")
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """A user follows a topic once."""
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
        """One read mark per user and topic."""
        constraints = [
            models.UniqueConstraint(fields=("user", "discussion"), name="forum_unique_read")
        ]


class Notification(models.Model):
    """Something for the user to read: a new post in a topic they follow, a new topic about a record they
    follow, a fix in the database, or a post to review."""

    class Kind(models.TextChoices):
        """Why the user is notified: reply, followed record, database fix, or post to review."""
        REPLY = "reply", "Reply"
        RECORD = "record", "New topic about a followed record"
        FIXED = "fixed", "Fixed in the database"
        REVIEW = "review", "Post awaiting review"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_notifications")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.REPLY)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Newest first; an index finds a user's unread ones; one per user, post and kind."""
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at"))]
        constraints = [
            models.UniqueConstraint(fields=("user", "post", "kind"), name="forum_unique_notification")
        ]


class GroupEmailSubscription(models.Model):
    """A user receives the posts of a group by email, one by one or in a weekly summary."""

    class Mode(models.TextChoices):
        """Every post in its own email, or a weekly summary."""
        EACH = "each", "Every post"
        WEEKLY = "weekly", "Weekly summary"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_group_emails")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="email_subscriptions")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.EACH)
    created_at = models.DateTimeField(auto_now_add=True)
    last_digest_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """One email subscription per user and group."""
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
    error = models.TextField(blank=True, db_collation=UTF8MB4)

    class Meta:
        """In queue order; a post is emailed to a user once."""
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(fields=("post", "user"), name="forum_unique_outgoing_email")
        ]


class IncomingEmail(models.Model):
    """Every message read from the forum mailbox, accepted or not, once per Message-ID."""

    class Status(models.TextChoices):
        """Accepted as a post, rejected with the reason, or ignored as an automatic message."""
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        IGNORED = "ignored", "Ignored"

    message_id = models.CharField(max_length=255, unique=True, db_collation=UTF8MB4)
    sender = models.CharField(max_length=255, db_collation=UTF8MB4)
    recipient = models.CharField(max_length=255, db_collation=UTF8MB4)
    subject = models.CharField(max_length=255, blank=True, db_collation=UTF8MB4)
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=255, blank=True, db_collation=UTF8MB4)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Newest messages first."""
        ordering = ("-received_at",)


def attachment_storage():
    """Outside MEDIA_ROOT, like VOTING_DIR: files of members-only groups go through the forum's checks."""
    return FileSystemStorage(location=getattr(
        settings, "FORUM_ATTACHMENTS_DIR", join(dirname(normpath(settings.MEDIA_ROOT)), "forum_attachments")))


def attachment_path(instance, filename):
    """A random file name in a year/month folder, with the extension of the given name lowercased."""
    return timezone.now().strftime("%Y/%m/") + uuid.uuid4().hex + splitext(filename)[1].lower()


class Attachment(models.Model):
    """An image or PDF sent with a post, from the web or by email."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(storage=attachment_storage, upload_to=attachment_path, max_length=200)
    # A still image of at most attachments.PREVIEW_SIZE pixels a side, shown in the post; the file itself
    # opens from it. Empty for PDFs and for small still images, which are shown as they are.
    preview = models.FileField(storage=attachment_storage, upload_to=attachment_path, max_length=200, blank=True)
    name = models.CharField(max_length=200, db_collation=UTF8MB4)
    # What the image shows, written by its author, for readers who cannot see it (the image's alt text).
    description = models.CharField(max_length=200, blank=True, db_collation=UTF8MB4)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """In the order they were added."""
        ordering = ("pk",)

    def __str__(self):
        """The file name readers see and download it under."""
        return self.name

    @property
    def is_image(self):
        """Whether the file is an image, by its content type; images show inline, other files download."""
        return self.content_type.startswith("image/")

    def get_absolute_url(self):
        """The URL that serves the file to those who may read its post."""
        return reverse("forum:attachment", kwargs={"pk": self.pk, "name": self.name})

    def get_preview_url(self):
        """The URL of the image shown in the post: its preview when it has one, else the file."""
        return self.get_absolute_url() + ("?preview=1" if self.preview else "")


class Poll(models.Model):
    """A poll in a topic; the members who can post in the group vote."""

    discussion = models.OneToOneField(Discussion, on_delete=models.CASCADE, related_name="poll")
    question = models.CharField(max_length=200, db_collation=UTF8MB4)
    multiple = models.BooleanField(default=False, help_text="Voters can choose more than one option.")
    closes_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_open(self):
        """Whether the poll takes votes: not closed by hand, and its closing time, if any, still ahead."""
        now = timezone.now()
        return self.closed_at is None and (self.closes_at is None or self.closes_at > now)


class PollOption(models.Model):
    """One of the answers a poll offers."""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=200, db_collation=UTF8MB4)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        """By position, the order the options were written in, then by id."""
        ordering = ("position", "pk")

    def __str__(self):
        """The option's text."""
        return self.text


class PollVote(models.Model):
    """A user's vote for one option; in a multiple-choice poll a user can vote for several."""
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_poll_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """A user votes for an option once."""
        constraints = [
            models.UniqueConstraint(fields=("option", "user"), name="forum_unique_poll_vote")
        ]


class PostVote(models.Model):
    """A user found the post helpful; each post shows how many did."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_post_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """A user votes for a post once."""
        constraints = [
            models.UniqueConstraint(
                fields=("post", "user"), name="forum_unique_post_vote"
            )
        ]


class Report(models.Model):
    """A user flags a topic or post to the moderators, with a reason."""
    class Status(models.TextChoices):
        """Open until handled; removing the content marks it actioned, dismissing it marks it dismissed.
        Reviewed is set only by hand, in the admin."""
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
    reason = models.TextField(max_length=1000, db_collation=UTF8MB4)
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
        """Newest first; a user reports a topic or post once; an index finds the reports about one."""
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("reporter", "content_type", "object_id"),
                name="forum_unique_report_per_content",
            )
        ]
        indexes = [models.Index(fields=("content_type", "object_id"))]

    def __str__(self):
        """The report number and its status label."""
        return f"Report #{self.pk} ({self.get_status_display()})"


class SuspensionQuerySet(models.QuerySet):
    """Queries on suspensions, with active() for those in force."""
    def active(self):
        """Suspensions with no end date or an end still in the future."""
        return self.filter(Q(until=None) | Q(until__gt=timezone.now()))


class Suspension(models.Model):
    """Posting privileges revoked for a user, in one group or in every group."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_suspensions")
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.CASCADE, related_name="suspensions",
        help_text="Leave empty to suspend the user in every group.")
    reason = models.TextField(db_collation=UTF8MB4)
    until = models.DateTimeField(null=True, blank=True, help_text="Leave empty for no end date.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="forum_suspensions_given")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SuspensionQuerySet.as_manager()

    class Meta:
        """Newest first."""
        ordering = ("-created_at",)

    def __str__(self):
        """The user and the group, or "every group" for a forum-wide suspension."""
        return f"{self.user} in {self.category or 'every group'}"


class ContentRevision(models.Model):
    """A recorded save of a topic or post: its audited fields before (empty on creation) and after,
    the user who made it, and the IP when known."""
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        """Newest first; an index finds the revisions of one topic or post (its history), and the edits of
        one user (access.edit_limit)."""
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("content_type", "object_id")),
                   models.Index(fields=("actor", "created_at"))]
