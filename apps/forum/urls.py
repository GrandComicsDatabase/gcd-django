from django.urls import path

from . import feeds, views
from .access import forum_view
from .attachments import files_follow_transaction

app_name = "forum"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", files_follow_transaction(views.DiscussionCreateView.as_view()), name="discussion-create"),
    path("feed/", feeds.LatestTopicsFeed(), name="feed"),
    path("groups/<slug:slug>/", views.group, name="group"),
    path("groups/<slug:slug>/feed/", feeds.GroupPostsFeed(), name="group-feed"),
    path("records/preview/", views.record_preview, name="record-preview"),
    path("records/search/", views.record_search, name="record-search"),
    path("preview/", views.markdown_preview, name="markdown-preview"),
    path("moderation/", views.moderation, name="moderation"),
    path("moderation/<int:pk>/", views.resolve_report, name="report-resolve"),
    path("moderation/posts/<int:pk>/", views.review_post, name="post-review"),
    path("attachments/<int:pk>/<str:name>", views.attachment, name="attachment"),
    path("notifications/", views.notifications, name="notifications"),
    path("email/unsubscribe/<int:user_id>/<str:kind>/<int:object_id>/<str:signature>/",
         views.email_unsubscribe, name="email-unsubscribe"),
    path("groups/<slug:slug>/email/", views.group_email, name="group-email"),
    path("notifications/read/", views.notifications_read, name="notifications-read"),
    path("records/<str:key>/<int:object_id>/", views.record, name="record"),
    path("records/<str:key>/<int:object_id>/follow/", views.follow_record, name="record-follow"),
    path("similar/", views.similar_topics, name="similar"),
    path("posts/<int:pk>/vote/", views.toggle_vote, name="post-vote"),
    path("posts/<int:pk>/edit/", views.PostUpdateView.as_view(), name="post-edit"),
    path("posts/<int:pk>/answer/", views.accept_answer, name="post-answer"),
    path("posts/<int:pk>/delete/", views.delete_post, name="post-delete"),
    path("posts/<int:pk>/history/", views.post_history, name="post-history"),
    path("report/<str:kind>/<int:pk>/", views.report_content, name="report"),
    path("<slug:slug>/", views.discussion_detail, name="discussion-detail"),
    path("<slug:slug>/reply/", views.reply, name="reply"),
    path("<slug:slug>/updates/", views.discussion_updates, name="discussion-updates"),
    path("<slug:slug>/poll/vote/", views.poll_vote, name="poll-vote"),
    path("<slug:slug>/poll/close/", views.poll_close, name="poll-close"),
    path("<slug:slug>/changes/", views.link_change, name="change-link"),
    path("<slug:slug>/changes/<int:pk>/remove/", views.unlink_change, name="change-unlink"),
    path("<slug:slug>/agenda/", views.link_agenda, name="agenda-link"),
    path("<slug:slug>/consensus/", views.seek_consensus, name="consensus-seek"),
    path("<slug:slug>/consensus/object/", views.object_to_consensus, name="consensus-object"),
    path("<slug:slug>/consensus/declare/", views.declare_consensus, name="consensus-declare"),
    path("<slug:slug>/edit/", views.DiscussionUpdateView.as_view(), name="discussion-edit"),
    path("<slug:slug>/move/", views.move_discussion, name="discussion-move"),
    path("<slug:slug>/moderate/", views.moderate_discussion, name="discussion-moderate"),
    path("<slug:slug>/follow/", views.toggle_follow, name="discussion-follow"),
    path("<slug:slug>/duplicate/", views.mark_duplicate, name="discussion-duplicate"),
    path("<slug:slug>/records/<int:pk>/remove/", views.remove_record, name="record-remove"),
    path("<slug:slug>/delete/", views.delete_discussion, name="discussion-delete"),
]

# The forum is for GCD users. These views also serve visitors when the admin opens a group to
# the public; the unsubscribe link of the emails works for everyone.
PUBLIC_VIEWS = {"index", "group", "record", "discussion-detail", "feed", "group-feed",
                "discussion-updates", "post-history", "attachment"}
ALWAYS_OPEN = {"email-unsubscribe"}
for pattern in urlpatterns:
    pattern.callback = forum_view(pattern.callback, public=pattern.name in PUBLIC_VIEWS,
                                  always=pattern.name in ALWAYS_OPEN)
