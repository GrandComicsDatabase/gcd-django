import json
import re

from django.test import Client
from django.urls import reverse

from apps.forum.models import Category, Discussion, Post, Suspension

from .base import ForumTestCase


class EditRightsTests(ForumTestCase):
    """Who may edit and move content: suspended authors may not, and authors never widen a topic's readers."""

    def test_suspended_authors_cannot_edit_or_move(self):
        """An author suspended in the group can neither edit their post or topic nor move it; the topic page
        offers them neither."""
        topic = self.make_topic("Mine", self.main, self.other)
        post = topic.posts.get()
        Suspension.objects.create(user=self.other, category=self.main, reason="Spam", created_by=self.author)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("forum:post-edit", args=[post.pk]),
                                          {"content": "New spam"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("forum:discussion-edit", args=[topic.slug])).status_code, 403)
        tech = Category.objects.get(slug="gcd-tech")
        self.assertEqual(self.client.post(reverse("forum:discussion-move", args=[topic.slug]),
                                          {"category": tech.pk}).status_code, 403)
        self.assertEqual(Post.objects.get(pk=post.pk).content, "First post")
        page = self.client.get(topic.get_absolute_url())
        self.assertNotContains(page, reverse("forum:post-edit", args=[post.pk]))
        self.assertNotContains(page, "Move to another group")

    def test_authors_never_move_a_topic_to_wider_readers(self):
        """The author of a members-only report cannot move it; from a group for GCD users they cannot move
        it into a group open to visitors. The group's moderators can."""
        error = Category.objects.get(slug="gcd-error")
        report = self.make_topic("Wrong cover", error, self.other)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:discussion-move", args=[report.slug]), {"category": self.main.pk})
        self.assertEqual(Discussion.objects.get(pk=report.pk).category, error)
        self.assertNotContains(self.client.get(report.get_absolute_url()), "Move to another group")
        tech = Category.objects.get(slug="gcd-tech")
        Category.objects.filter(pk=tech.pk).update(read_access=Category.Access.PUBLIC)
        topic = self.make_topic("Mine", self.main, self.other)
        self.client.post(reverse("forum:discussion-move", args=[topic.slug]), {"category": tech.pk})
        self.assertEqual(Discussion.objects.get(pk=topic.pk).category, self.main)
        error.moderators.add(self.author)
        error.members.add(self.author)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-move", args=[report.slug]), {"category": self.main.pk})
        self.assertEqual(Discussion.objects.get(pk=report.pk).category, self.main)


class VisitorPrivacyTests(ForumTestCase):
    """What visitors can learn once the admin opens a group to them."""

    def setUp(self):
        """Open gcd-main to visitors."""
        super().setUp()
        Category.objects.filter(pk=self.main.pk).update(read_access=Category.Access.PUBLIC)

    def test_visitors_cannot_tell_whether_a_hidden_topic_exists(self):
        """A members-only topic and a topic that does not exist give a visitor the same sign-in page."""
        hidden = self.make_topic("Ban user jsmith", Category.objects.get(slug="gcd-editor"), self.author)
        visitor = Client()
        existing = visitor.get(reverse("forum:discussion-detail", args=[hidden.slug]))
        missing = visitor.get(reverse("forum:discussion-detail", args=["no-such-topic"]))
        self.assertEqual((existing.status_code, missing.status_code), (403, 403))
        self.assertContains(missing, "Sign in", status_code=403)

    def test_structured_data_leaves_out_a_removed_first_post(self):
        """When the first post of a public topic is removed, the page has no schema.org data with its text."""
        self.post.delete()
        Post.objects.create(discussion=self.discussion, author=self.other, content="A reply",
                            created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
        page = Client().get(self.discussion.get_absolute_url()).content.decode()
        found = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        self.assertTrue(found is None or "First post" not in json.loads(found.group(1)).get("text", ""))
        self.assertNotIn("First post", page)


class TopicMarkTests(ForumTestCase):
    """Record links and duplicate marks follow who may edit and who may read."""

    def test_suspended_authors_cannot_unlink_records(self):
        """An author suspended in the group can no longer remove the records linked to their topic."""
        from apps.forum.models import DiscussionRecord
        from apps.forum.records import record_content_type

        topic = self.make_topic("Mine", self.main, self.other)
        link = DiscussionRecord.objects.create(discussion=topic, content_type=record_content_type("publisher"),
                                               object_id=self.make_publisher().pk, created_by=self.other)
        Suspension.objects.create(user=self.other, category=self.main, reason="Spam", created_by=self.author)
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:record-remove", args=[topic.slug, link.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(DiscussionRecord.objects.filter(pk=link.pk).exists())

    def test_duplicate_chains_stop_at_topics_the_moderator_cannot_read(self):
        """Closing A as a duplicate of B, itself a duplicate of a removed C, points A to B, not to C."""
        self.main.moderators.add(self.author)
        first, middle, gone = (self.make_topic(title, self.main, self.other) for title in ("A", "B", "C"))
        Discussion.all_objects.filter(pk=middle.pk).update(duplicate_of=gone, is_locked=True)
        gone.delete()
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-duplicate", args=[first.slug]),
                         {"original": middle.get_absolute_url()})
        self.assertEqual(Discussion.objects.get(pk=first.pk).duplicate_of_id, middle.pk)

    def test_the_duplicate_banner_names_only_an_original_the_reader_can_read(self):
        """A reader who cannot read the original sees "Closed as a duplicate." without its title or link."""
        editors = Category.objects.get(slug="gcd-editor")
        hidden = self.make_topic("Editors only plan", editors, self.author)
        Discussion.all_objects.filter(pk=self.discussion.pk).update(duplicate_of=hidden, is_locked=True)
        self.client.force_login(self.other)
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(page, "Closed as a duplicate.")
        self.assertNotContains(page, "Editors only plan")
