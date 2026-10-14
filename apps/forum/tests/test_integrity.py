from datetime import timedelta
from importlib import import_module
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection, migrations
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.forum.access import posting_limit
from apps.forum.activity import unread_notifications
from apps.forum.models import Category, Discussion, Objection, Post, Report, TopicRead, TopicSubscription
from apps.forum.procedure import consensus_state
from apps.forum.views import DiscussionUpdateView, PostUpdateView

from .base import ForumTestCase


class StateTests(ForumTestCase):
    """Moderator actions and edits work on the topic as it is now, and keep its marks consistent."""

    def reply(self, user, content="A reply"):
        """A published reply to the test topic by the user."""
        return Post.objects.create(discussion=self.discussion, author=user, content=content,
                                   created_by=user, updated_by=user, ip_address="127.0.0.1")

    @override_settings(FORUM_REVIEW_FIRST_POSTS=True)
    def test_a_held_post_is_decided_once(self):
        """When a second moderator rejects a post another one already published, the post stays published
        and the second is told it was handled."""
        self.main.moderators.add(self.author)
        newcomer = get_user_model().objects.create_user("newcomer", password="x")
        self.client.force_login(newcomer)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "First words"})
        held = Post.all_objects.get(author=newcomer)
        self.client.force_login(self.author)
        url = reverse("forum:post-review", args=[held.pk])
        self.client.post(url, {"action": "approve"})
        response = self.client.post(url, {"action": "reject"}, follow=True)
        self.assertContains(response, "no longer waiting for review")
        held.refresh_from_db()
        self.assertEqual((held.awaiting_review, held.is_deleted), (False, False))

    def test_the_answer_follows_the_topic_marks(self):
        """An archived topic takes no answer; unmarking an answer leaves a fixed topic resolved; removing the
        answer clears it and reopens a topic nothing else solved."""
        answer = self.reply(self.other)
        self.client.force_login(self.author)
        url = reverse("forum:post-answer", args=[answer.pk])
        Discussion.all_objects.filter(pk=self.discussion.pk).update(status=Discussion.Status.ARCHIVED)
        self.client.post(url)
        self.assertEqual(Discussion.objects.get(pk=self.discussion.pk).answer_id, None)
        Discussion.all_objects.filter(pk=self.discussion.pk).update(
            status=Discussion.Status.RESOLVED, consensus_passed_at=timezone.now())
        self.client.post(url)
        self.client.post(url)
        topic = Discussion.objects.get(pk=self.discussion.pk)
        self.assertEqual((topic.answer_id, topic.status), (None, Discussion.Status.RESOLVED))
        Discussion.all_objects.filter(pk=topic.pk).update(consensus_passed_at=None)
        self.client.post(url)
        Post.objects.get(pk=answer.pk).delete()
        topic = Discussion.objects.get(pk=topic.pk)
        self.assertEqual((topic.answer_id, topic.status), (None, Discussion.Status.OPEN))

    def test_edits_do_not_undo_changes_made_meanwhile(self):
        """A title or post edit sent from a page loaded before a move or a removal changes only the text."""
        tech = Category.objects.get(slug="gcd-tech")
        stale_topic = Discussion.objects.get(pk=self.discussion.pk)
        Discussion.all_objects.filter(pk=self.discussion.pk).update(category=tech)
        self.client.force_login(self.author)
        with mock.patch.object(DiscussionUpdateView, "get_object", return_value=stale_topic):
            self.client.post(reverse("forum:discussion-edit", args=[self.discussion.slug]),
                             {"title": "A better title", "records": ""})
        topic = Discussion.all_objects.get(pk=self.discussion.pk)
        self.assertEqual((topic.title, topic.category), ("A better title", tech))
        stale_post = Post.objects.get(pk=self.post.pk)
        Post.all_objects.filter(pk=self.post.pk).update(is_deleted=True)
        with mock.patch.object(PostUpdateView, "get_object", return_value=stale_post):
            self.client.post(reverse("forum:post-edit", args=[self.post.pk]), {"content": "Edited"})
        post = Post.all_objects.get(pk=self.post.pk)
        self.assertEqual((post.content, post.is_deleted), ("Edited", True))

    def test_duplicates_never_point_at_each_other_and_reopening_clears_the_mark(self):
        """Closing B as a duplicate of A, when A is a duplicate of B, is refused; reopening clears the mark."""
        self.main.moderators.add(self.author)
        other = self.make_topic("Same question", self.main, self.other)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-duplicate", args=[self.discussion.slug]),
                         {"original": other.get_absolute_url()})
        response = self.client.post(reverse("forum:discussion-duplicate", args=[other.slug]),
                                    {"original": self.discussion.get_absolute_url()}, follow=True)
        self.assertContains(response, "itself closed as a duplicate of this one")
        self.assertIsNone(Discussion.objects.get(pk=other.pk).duplicate_of_id)
        self.client.post(reverse("forum:discussion-moderate", args=[self.discussion.slug]), {"action": "reopen"})
        topic = Discussion.objects.get(pk=self.discussion.pk)
        self.assertEqual((topic.is_locked, topic.duplicate_of_id), (False, None))

    def test_a_removed_objection_is_withdrawn(self):
        """Removing an objection's post withdraws it: the consensus is no longer at an impasse, and the member
        may object again."""
        Discussion.all_objects.filter(pk=self.discussion.pk).update(
            consensus_sought_at=timezone.now() - timedelta(days=1), consensus_sought_by=self.author)
        post = self.reply(self.other, "**Objection:** Too strict.")
        Objection.objects.create(discussion=self.discussion, user=self.other, post=post)
        self.assertEqual(consensus_state(Discussion.objects.get(pk=self.discussion.pk))["state"], "impasse")
        post.delete()
        self.assertEqual(consensus_state(Discussion.objects.get(pk=self.discussion.pk))["state"], "waiting")
        self.client.force_login(self.other)
        self.client.post(reverse("forum:consensus-object", args=[self.discussion.slug]), {"reason": "Still."})
        self.assertEqual(Objection.objects.get(user=self.other).post.content, "**Objection:** Still.")

    def test_posting_limits_lock_no_user_row(self):
        """The limit check takes no lock on the user's row: notifications and emails for that user, inserted
        by other posts while their topic is locked, take a shared lock on it, and the two would deadlock."""
        with CaptureQueriesContext(connection) as queries:
            posting_limit(self.other)
        self.assertFalse(any("FOR UPDATE" in query["sql"] for query in queries))

    def test_the_badge_counts_what_the_list_shows(self):
        """A notification of a topic removed since is neither listed nor counted in the badge."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hi"})
        self.assertEqual(unread_notifications(self.author).count(), 1)
        Discussion.objects.get(pk=self.discussion.pk).delete()
        self.assertEqual(unread_notifications(self.author).count(), 0)

    @override_settings(FORUM_REVIEW_FIRST_POSTS=True)
    def test_review_requests_and_approved_posts(self):
        """Opening a topic leaves a moderator's review request unread; the Moderation page marks it read before
        the badge is counted. An approved post comes at the end of the topic, and the posts a reader read after
        it stay read: a read mark is the highest post id read, so it is not lowered for the approved post."""
        self.main.moderators.add(self.author)
        newcomer = get_user_model().objects.create_user("newcomer", password="x")
        self.client.force_login(newcomer)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Held words"})
        held = Post.all_objects.get(author=newcomer)
        later = self.reply(self.other, "A later reply")
        self.client.force_login(self.author)
        self.client.get(self.discussion.get_absolute_url())
        self.assertEqual(unread_notifications(self.author).filter(kind="review").count(), 1)
        response = self.client.get(reverse("forum:moderation"))
        self.assertEqual(response.context["notification_count"], 0)
        self.client.force_login(self.other)
        self.client.get(self.discussion.get_absolute_url())
        self.client.force_login(self.author)
        self.client.post(reverse("forum:post-review", args=[held.pk]), {"action": "approve"})
        held.refresh_from_db()
        self.assertGreater(held.created_at, later.created_at)
        self.client.force_login(self.other)
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertIsNone(page.context["first_unread"])
        self.assertEqual([post.pk for post in page.context["post_roots"]][-1], held.pk)

    def test_unread_marks_survive_the_topics_own_links(self):
        """Following "Go to the first unread post" keeps the posts unread, and a removed post is never one."""
        TopicRead.objects.create(user=self.author, discussion=self.discussion, last_read_post_id=self.post.pk)
        first = self.reply(self.other, "One")
        removed = self.reply(self.other, "Two")
        removed.delete()
        self.client.force_login(self.author)
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertEqual(page.context["first_unread"].pk, first.pk)
        self.assertContains(page, f'href="#post-{first.pk}">Go to the first unread post')
        again = self.client.get(self.discussion.get_absolute_url(), {"post": first.pk, "since": self.post.pk})
        unread = [post.pk for root in again.context["post_roots"] for post in [root, *root.tree_children]
                  if post.is_unread]
        self.assertEqual(unread, [first.pk])

    def test_removing_content_closes_its_reports(self):
        """A moderator removing a reported post from its menu marks its open reports handled."""
        post = self.reply(self.other, "Spam")
        self.client.force_login(self.author)
        self.client.post(reverse("forum:report", args=["post", post.pk]), {"reason": "Spam"})
        self.main.moderators.add(self.author)
        self.client.post(reverse("forum:post-delete", args=[post.pk]))
        self.assertEqual(Report.objects.get().status, Report.Status.ACTIONED)

    def test_a_reply_to_a_removed_post_says_so(self):
        """A reply to a post removed meanwhile is sent back saying what happened and what to do."""
        post = self.reply(self.author)
        post.delete()
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "An answer", "parent": post.pk})
        self.assertContains(response, "The post you were answering was removed", status_code=422)

    def test_rolling_back_migration_0005_opens_nothing(self):
        """Migration 0005 cannot be reversed into opening groups to visitors: its reverse does nothing."""
        migration = import_module("apps.forum.migrations.0005_groups_for_gcd_users").Migration
        self.assertIs(migration.operations[0].reverse_code, migrations.RunPython.noop)
