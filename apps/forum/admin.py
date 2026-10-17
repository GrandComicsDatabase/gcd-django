from django.contrib import admin
from django.utils import timezone

from .models import (
    Category, ContentRevision, Discussion, DiscussionRecord, IncomingEmail, Objection, OutgoingEmail, Post,
    PostVote, Report, Suspension,
)
from .audit import request_audit
from .utils import get_client_ip


class ContentAdmin(admin.ModelAdmin):
    """Base admin of topics and posts: no adding, and authorship, IP, dates and removal flag read-only.
    Deleting here is a soft delete; the revisions of edits and removals record the admin user and their IP."""
    readonly_fields = (
        "author", "created_by", "updated_by", "ip_address",
        "created_at", "updated_at", "deleted_at", "is_deleted",
    )

    def has_add_permission(self, request):
        """Topics and posts come from the forum; the admin cannot set their read-only author and IP."""
        return False

    def save_model(self, request, obj, form, change):
        """Save with the admin user as updated_by; a revision of the change records them and their IP."""
        obj.updated_by = request.user
        token = request_audit.set((request.user.pk, get_client_ip(request)))
        try:
            super().save_model(request, obj, form, change)
        finally:
            request_audit.reset(token)

    def delete_model(self, request, obj):
        """Remove one object as the bulk action does: a soft delete by the admin user."""
        self.delete_queryset(request, self.model.all_objects.filter(pk=obj.pk))

    def delete_queryset(self, request, queryset):
        """Soft-delete each object as changed by the admin user, whose id and IP the revisions record."""
        token = request_audit.set((request.user.pk, get_client_ip(request)))
        try:
            for obj in queryset:
                obj.updated_by = request.user
                obj.save(update_fields=("updated_by", "updated_at"))
                obj.delete()
        finally:
            request_audit.reset(token)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin of the groups: position and active flag edited from the list, slug prefilled from the name."""
    list_display = ("name", "section", "position", "is_active", "read_access", "post_access")
    # Production has hundreds of thousands of accounts: ids, not lists of every account.
    raw_id_fields = ("members", "moderators")
    list_filter = ("section", "read_access", "post_access")
    list_editable = ("position", "is_active")
    prepopulated_fields = {"slug": ("name",)}


class DiscussionRecordInline(admin.TabularInline):
    """The records a topic is linked to, on the topic's admin page, with read-only fields."""
    model = DiscussionRecord
    extra = 0
    readonly_fields = ("content_type", "object_id", "created_by", "created_at")

    def has_add_permission(self, request, obj=None):
        """Records are linked from the forum; the link fields are read-only here."""
        return False


@admin.register(Discussion)
class DiscussionAdmin(ContentAdmin):
    """Admin of topics, removed ones included, with the records each is linked to."""
    list_display = (
        "title",
        "author",
        "category",
        "status",
        "is_pinned",
        "is_locked",
        "is_deleted",
        "created_at",
    )
    list_filter = ("status", "is_pinned", "is_locked", "is_deleted", "category")
    search_fields = ("title", "author__username")
    # Counters and the marks the forum's own actions set are read-only: a form opened before a reply, a
    # review or an accepted answer would write their old values back. Held topics are published from the
    # Moderation page, which also notifies and emails.
    readonly_fields = ContentAdmin.readonly_fields + (
        "slug", "moved_from", "moved_by", "moved_at", "post_count", "last_activity", "views_count",
        "awaiting_review", "answer", "fixed_by", "consensus_sought_at", "consensus_sought_by",
        "consensus_passed_at")
    # Ids, not lists of every topic, agenda item or ballot of the site.
    raw_id_fields = ("duplicate_of", "agenda_item", "ballot")
    inlines = (DiscussionRecordInline,)

    def get_queryset(self, request):
        """Every topic, also removed or awaiting review, with its author and group in the same query."""
        return Discussion.all_objects.select_related("author", "category")


@admin.register(Post)
class PostAdmin(ContentAdmin):
    """Admin of posts, removed ones included; their topic and parent are read-only."""
    list_display = ("id", "discussion", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("content", "author__username", "discussion__title")
    # A held post is published from the Moderation page, which also notifies and emails.
    readonly_fields = ContentAdmin.readonly_fields + ("discussion", "parent", "awaiting_review")

    def get_queryset(self, request):
        """Every post, also removed or awaiting review, with its author and topic in the same query."""
        return Post.all_objects.select_related("author", "discussion")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin of reports: only the status is editable, and changing it records who reviewed it and when."""
    list_display = ("id", "reporter", "content_type", "object_id", "status", "created_at")
    list_filter = ("status", "content_type")
    search_fields = ("reason", "reporter__username")
    readonly_fields = (
        "reporter", "content_type", "object_id", "reason", "created_at",
        "reviewed_by", "reviewed_at",
    )

    def has_add_permission(self, request):
        """Reports are sent from the forum; here only their status can be changed."""
        return False

    def save_model(self, request, obj, form, change):
        """When the status changes, record the admin user and the time as the review."""
        if "status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Suspension)
class SuspensionAdmin(admin.ModelAdmin):
    """Admin of suspensions: the user is picked by id, and the admin user who adds one is recorded."""
    list_display = ("user", "category", "until", "created_by", "created_at")
    list_filter = ("category",)
    search_fields = ("user__username", "reason")
    raw_id_fields = ("user",)
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        """A new suspension is recorded as given by the admin user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(OutgoingEmail)
class OutgoingEmailAdmin(admin.ModelAdmin):
    """The outgoing email queue, read-only: when each email was sent, its attempts and last error."""
    list_display = ("post", "user", "created_at", "sent_at", "attempts")
    list_filter = ("sent_at",)
    readonly_fields = ("post", "user", "created_at", "sent_at", "attempts", "error")

    def has_add_permission(self, request):
        """The forum queues the emails; every field is read-only here."""
        return False


@admin.register(IncomingEmail)
class IncomingEmailAdmin(admin.ModelAdmin):
    """The log of incoming emails, read-only; search by sender, subject or Message-ID."""
    list_display = ("received_at", "sender", "recipient", "subject", "status", "reason")
    list_filter = ("status",)
    search_fields = ("sender", "subject", "message_id")
    readonly_fields = ("message_id", "sender", "recipient", "subject", "status", "reason", "post", "received_at")

    def has_add_permission(self, request):
        """The forum logs each email it reads; every field is read-only here."""
        return False


@admin.register(PostVote)
class PostVoteAdmin(admin.ModelAdmin):
    """Helpful votes, with the post and the voter as ids rather than lists of every post and account."""
    list_display = ("post", "user", "created_at")
    raw_id_fields = ("post", "user")


@admin.register(Objection)
class ObjectionAdmin(admin.ModelAdmin):
    """Objections to consensus; deleting one withdraws it, as removing its post does."""
    list_display = ("discussion", "user", "created_at")
    raw_id_fields = ("discussion", "user", "post")


@admin.register(ContentRevision)
class ContentRevisionAdmin(admin.ModelAdmin):
    """The audit trail of topics and posts: the admin views it, and only superusers may delete a revision."""
    list_display = ("id", "content_type", "object_id", "actor", "created_at")
    readonly_fields = ("content_type", "object_id", "actor", "ip_address", "created_at", "before", "after")

    def has_add_permission(self, request):
        """Revisions are recorded only by saving a topic or post."""
        return False

    def has_change_permission(self, request, obj=None):
        """Revisions cannot be edited, so the audit trail stays as recorded."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers delete a revision, to redact text that must not stay (personal data); the rest
        of the audit trail stays as recorded."""
        return request.user.is_superuser
