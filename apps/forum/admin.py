from django.contrib import admin
from django.utils import timezone

from .models import (
    Category, ContentRevision, Discussion, DiscussionRecord, IncomingEmail, OutgoingEmail, Post, PostVote,
    Report, Suspension,
)
from .audit import request_audit
from .utils import get_client_ip


class ContentAdmin(admin.ModelAdmin):
    readonly_fields = (
        "author", "created_by", "updated_by", "ip_address",
        "created_at", "updated_at", "deleted_at", "is_deleted",
    )

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        token = request_audit.set((request.user.pk, get_client_ip(request)))
        try:
            super().save_model(request, obj, form, change)
        finally:
            request_audit.reset(token)

    def delete_model(self, request, obj):
        self.delete_queryset(request, self.model.all_objects.filter(pk=obj.pk))

    def delete_queryset(self, request, queryset):
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
    list_display = ("name", "section", "position", "is_active", "read_access", "post_access")
    filter_horizontal = ("members", "moderators")
    list_filter = ("section", "read_access", "post_access")
    list_editable = ("position", "is_active")
    prepopulated_fields = {"slug": ("name",)}


class DiscussionRecordInline(admin.TabularInline):
    model = DiscussionRecord
    extra = 0
    readonly_fields = ("content_type", "object_id", "created_by", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Discussion)
class DiscussionAdmin(ContentAdmin):
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
    readonly_fields = ContentAdmin.readonly_fields + ("slug", "moved_from", "moved_by", "moved_at")
    inlines = (DiscussionRecordInline,)

    def get_queryset(self, request):
        return Discussion.all_objects.select_related("author", "category")


@admin.register(Post)
class PostAdmin(ContentAdmin):
    list_display = ("id", "discussion", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("content", "author__username", "discussion__title")
    readonly_fields = ContentAdmin.readonly_fields + ("discussion", "parent")

    def get_queryset(self, request):
        return Post.all_objects.select_related("author", "discussion")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "content_type", "object_id", "status", "created_at")
    list_filter = ("status", "content_type")
    search_fields = ("reason", "reporter__username")
    readonly_fields = (
        "reporter", "content_type", "object_id", "reason", "created_at",
        "reviewed_by", "reviewed_at",
    )

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Suspension)
class SuspensionAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "until", "created_by", "created_at")
    list_filter = ("category",)
    search_fields = ("user__username", "reason")
    raw_id_fields = ("user",)
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(OutgoingEmail)
class OutgoingEmailAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "created_at", "sent_at", "attempts")
    list_filter = ("sent_at",)
    readonly_fields = ("post", "user", "created_at", "sent_at", "attempts", "error")

    def has_add_permission(self, request):
        return False


@admin.register(IncomingEmail)
class IncomingEmailAdmin(admin.ModelAdmin):
    list_display = ("received_at", "sender", "recipient", "subject", "status", "reason")
    list_filter = ("status",)
    search_fields = ("sender", "subject", "message_id")
    readonly_fields = ("message_id", "sender", "recipient", "subject", "status", "reason", "post", "received_at")

    def has_add_permission(self, request):
        return False


admin.site.register(PostVote)


@admin.register(ContentRevision)
class ContentRevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "content_type", "object_id", "actor", "created_at")
    readonly_fields = ("content_type", "object_id", "actor", "ip_address", "created_at", "before", "after")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
