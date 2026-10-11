from django.urls import path

from . import views
from .access import forum_view

app_name = "forum"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.DiscussionCreateView.as_view(), name="discussion-create"),
    path("groups/<slug:slug>/", views.group, name="group"),
    path("records/preview/", views.record_preview, name="record-preview"),
    path("notifications/", views.notifications, name="notifications"),
    path("email/unsubscribe/<int:user_id>/<str:kind>/<int:object_id>/<str:signature>/",
         views.email_unsubscribe, name="email-unsubscribe"),
    path("groups/<slug:slug>/email/", views.toggle_group_email, name="group-email"),
    path("notifications/read/", views.notifications_read, name="notifications-read"),
    path("records/<str:key>/<int:object_id>/", views.record, name="record"),
    path("posts/<int:pk>/vote/", views.toggle_vote, name="post-vote"),
    path("posts/<int:pk>/edit/", views.PostUpdateView.as_view(), name="post-edit"),
    path("posts/<int:pk>/answer/", views.accept_answer, name="post-answer"),
    path("posts/<int:pk>/delete/", views.delete_post, name="post-delete"),
    path("report/<str:kind>/<int:pk>/", views.report_content, name="report"),
    path("<slug:slug>/", views.discussion_detail, name="discussion-detail"),
    path("<slug:slug>/reply/", views.reply, name="reply"),
    path("<slug:slug>/edit/", views.DiscussionUpdateView.as_view(), name="discussion-edit"),
    path("<slug:slug>/move/", views.move_discussion, name="discussion-move"),
    path("<slug:slug>/moderate/", views.moderate_discussion, name="discussion-moderate"),
    path("<slug:slug>/follow/", views.toggle_follow, name="discussion-follow"),
    path("<slug:slug>/duplicate/", views.mark_duplicate, name="discussion-duplicate"),
    path("<slug:slug>/records/<int:pk>/remove/", views.remove_record, name="record-remove"),
    path("<slug:slug>/delete/", views.delete_discussion, name="discussion-delete"),
]

# Public lists can be read without an account; everything else needs one.
PUBLIC_VIEWS = {"index", "group", "record", "discussion-detail", "email-unsubscribe"}
for pattern in urlpatterns:
    pattern.callback = forum_view(pattern.callback, public=pattern.name in PUBLIC_VIEWS)
