from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.forum.forms import PostForm
from apps.forum.models import Category, ContentRevision, Discussion, Post, PostVote

from .base import ForumTestCase


class TopicTests(ForumTestCase):
    def test_create_topic_and_reply_with_audit(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "A new topic", "content": "A question",
        }, REMOTE_ADDR="192.0.2.5")
        self.assertEqual(response.status_code, 302)
        topic = Discussion.objects.get(title="A new topic")
        self.assertEqual(topic.created_by, self.other)
        self.assertEqual(topic.ip_address, "192.0.2.5")
        response = self.client.post(reverse("forum:reply", args=[topic.slug]), {"content": "A reply"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(topic.posts.count(), 2)

    def test_slug_and_soft_delete_preserve_record(self):
        self.assertEqual(self.discussion.slug, "a-forum-topic")
        self.discussion.delete()
        self.assertFalse(Discussion.objects.filter(pk=self.discussion.pk).exists())
        self.assertTrue(Discussion.all_objects.get(pk=self.discussion.pk).is_deleted)

    def test_reserved_path_gets_another_slug(self):
        topic = self.make_topic("Records", self.main, self.author)
        self.assertEqual(topic.slug, "records-discussion")

    def test_vote_toggles_one_vote_per_user(self):
        self.client.force_login(self.other)
        url = reverse("forum:post-vote", args=(self.post.pk,))
        self.assertEqual(self.client.post(url, HTTP_HX_REQUEST="true").status_code, 200)
        self.assertEqual(PostVote.objects.filter(post=self.post, user=self.other).count(), 1)
        self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertFalse(PostVote.objects.filter(post=self.post, user=self.other).exists())

    def test_only_author_or_staff_can_remove_post(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("forum:post-delete", args=(self.post.pk,))).status_code, 403)
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(reverse("forum:post-delete", args=(self.post.pk,))).status_code, 302)
        self.assertTrue(Post.all_objects.get(pk=self.post.pk).is_deleted)

    def test_reply_rejects_parent_from_another_discussion(self):
        foreign_post = self.make_topic("Other topic", self.main, self.author).posts.get()
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:reply", args=(self.discussion.slug,)),
                                    {"content": "Reply", "parent": foreign_post.pk}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.discussion.posts.count(), 1)

    def test_reply_parent_is_hidden(self):
        self.assertTrue(PostForm(discussion=self.discussion)["parent"].is_hidden)

    def test_locked_and_deleted_topics_reject_writes(self):
        self.discussion.is_locked = True
        self.discussion.save()
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:reply", args=(self.discussion.slug,)), {"content": "Blocked"})
        self.assertEqual(response.status_code, 403)
        self.discussion.delete()
        for route in ("post-vote", "post-delete", "post-edit"):
            self.assertEqual(self.client.post(reverse(f"forum:{route}", args=(self.post.pk,))).status_code, 404)

    def test_edit_and_remove_keep_revision_and_actor(self):
        self.client.force_login(self.author)
        self.client.post(reverse("forum:post-edit", args=[self.post.pk]),
                         {"content": "Edited text"}, REMOTE_ADDR="192.0.2.8")
        revision = ContentRevision.objects.filter(
            content_type=ContentType.objects.get_for_model(Post), object_id=self.post.pk).first()
        self.assertEqual(revision.before["content"], "First post")
        self.assertEqual(revision.after["content"], "Edited text")
        self.assertEqual(revision.actor, self.author)
        self.assertEqual(revision.ip_address, "192.0.2.8")


class MoveTests(ForumTestCase):
    def test_moved_topic_leaves_a_pointer_in_the_old_group(self):
        policy = Category.objects.get(slug="gcd-policy")
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:discussion-move", args=[self.discussion.slug]),
                                    {"category": policy.pk})
        self.assertEqual(response.status_code, 302)
        self.discussion.refresh_from_db()
        self.assertEqual(self.discussion.category, policy)
        self.assertEqual(self.discussion.moved_from, self.main)
        self.assertEqual(self.discussion.moved_by, self.author)
        self.assertContains(self.client.get(self.main.get_absolute_url()), "Moved to gcd-policy")
        self.assertContains(self.client.get(self.discussion.get_absolute_url()), "Moved from")

    def test_only_author_or_staff_can_move(self):
        policy = Category.objects.get(slug="gcd-policy")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-move", args=[self.discussion.slug]),
                                    {"category": policy.pk})
        self.assertEqual(response.status_code, 403)

    def test_cannot_move_into_a_group_without_post_access(self):
        editor = Category.objects.get(slug="gcd-editor")
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:discussion-move", args=[self.discussion.slug]),
                                    {"category": editor.pk})
        self.assertEqual(response.status_code, 400)
        self.discussion.refresh_from_db()
        self.assertEqual(self.discussion.category, self.main)


class TopicListTests(ForumTestCase):
    def test_counters_follow_new_and_removed_posts(self):
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "A reply"})
        reply = self.discussion.posts.latest("pk")
        self.discussion.refresh_from_db()
        self.assertEqual((self.discussion.post_count, self.discussion.last_activity), (2, reply.created_at))
        reply.delete()
        self.discussion.refresh_from_db()
        self.assertEqual((self.discussion.post_count, self.discussion.last_activity), (1, self.post.created_at))

    def test_topic_list_queries_do_not_grow_with_topics(self):
        self.client.force_login(self.other)
        self.client.get(reverse("forum:index"))
        with CaptureQueriesContext(connection) as one_topic:
            self.client.get(reverse("forum:index"))
        for number in range(10):
            self.make_topic(f"Topic {number}", self.main, self.author)
        with self.assertNumQueries(len(one_topic)):
            response = self.client.get(reverse("forum:index"))
        self.assertEqual(response.context["discussions"][0].title, "Topic 9")


@override_settings(FORUM_MAX_TOPICS_PER_DAY=1, FORUM_MAX_POSTS_PER_DAY=3)
class PostingLimitTests(ForumTestCase):
    def test_topics_and_replies_are_limited_per_day(self):
        self.client.force_login(self.other)
        create = reverse("forum:discussion-create")
        self.client.post(create, {"category": self.main.pk, "title": "First", "content": "One"})
        response = self.client.post(create, {"category": self.main.pk, "title": "Second", "content": "Two"})
        self.assertContains(response, "at most 1 topics in 24 hours")
        reply = reverse("forum:reply", args=[self.discussion.slug])
        for number in range(3):
            self.client.post(reply, {"content": f"Reply {number}"})
        self.assertEqual(Post.all_objects.filter(author=self.other).count(), 3)
        response = self.client.post(reply, {"content": "One too many"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "at most 3 messages in 24 hours", status_code=422)

    def test_removing_posts_does_not_reset_the_limit_and_staff_are_free(self):
        self.client.force_login(self.other)
        reply = reverse("forum:reply", args=[self.discussion.slug])
        for number in range(3):
            self.client.post(reply, {"content": f"Reply {number}"})
        Post.objects.filter(author=self.other).delete()
        self.assertEqual(self.client.post(reply, {"content": "Again"}).status_code, 422)
        self.other.is_staff = True
        self.other.save()
        self.assertEqual(self.client.post(reply, {"content": "Staff"}).status_code, 302)
