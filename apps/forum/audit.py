from contextvars import ContextVar

request_audit = ContextVar("forum_request_audit", default=None)


def snapshot(instance):
    """The audited fields a topic or post has, with their values, as the dict a ContentRevision stores."""
    fields = ("title", "content", "author_id", "category_id", "discussion_id", "parent_id",
              "moved_from_id", "answer_id", "duplicate_of_id", "is_deleted", "awaiting_review", "is_locked",
              "is_pinned", "status",
              "created_by_id", "updated_by_id", "ip_address")
    return {field: getattr(instance, field) for field in fields if hasattr(instance, field)}
