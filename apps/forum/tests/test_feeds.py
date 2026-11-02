import json
import re
from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.forum import mail as gateway
from apps.forum.models import Category, GroupEmailSubscription, OutgoingEmail, Post

from .base import ForumTestCase


class FeedTests(ForumTestCase):
    """Feeds and structured data exist for the groups the admin opens to the public."""

    def setUp(self):
        """Open gcd-main to the public, as the admin can."""
        super().setUp()
        Category.objects.filter(pk=self.main.pk).update(read_access=Category.Access.PUBLIC)

    def test_no_feed_while_no_group_is_public(self):
        """While no group is public, a visitor asking for the feed gets the sign-in page with 403."""
        Category.objects.filter(pk=self.main.pk).update(read_access=Category.Access.USERS)
        self.assertContains(self.client.get(reverse("forum:feed")), "Sign in", status_code=403)

    def test_public_feeds_list_topics_and_posts(self):
        """The Atom feed lists public topics as "[group] title"; a group feed has the text of its posts."""
        response = self.client.get(reverse("forum:feed"))
        self.assertEqual(response["Content-Type"], "application/atom+xml; charset=utf-8")
        self.assertContains(response, "[gcd-main] A forum topic")
        response = self.client.get(reverse("forum:group-feed", args=["gcd-main"]))
        self.assertContains(response, "First post")

    def test_member_only_groups_have_no_feed_and_stay_out_of_the_feed(self):
        """A members-only group has no feed (404); its topics stay out of the forum feed, even for members."""
        editor = Category.objects.get(slug="gcd-editor")
        self.make_topic("Editors only", editor, self.author)
        self.assertEqual(self.client.get(reverse("forum:group-feed", args=["gcd-editor"])).status_code, 404)
        self.client.force_login(self.author)
        editor.members.add(self.author)
        self.assertNotContains(self.client.get(reverse("forum:feed")), "Editors only")

    def test_public_topic_has_structured_data_safe_from_html(self):
        """A public topic has schema.org data where even a "</script>" title cannot end the script element."""
        topic = self.make_topic("</script><b>x</b>", self.main, self.author)
        response = self.client.get(topic.get_absolute_url())
        found = re.search(r'<script type="application/ld\+json">(.*?)</script>', response.content.decode(), re.S)
        data = json.loads(found.group(1))
        self.assertEqual((data["@type"], data["headline"]), ("DiscussionForumPosting", "</script><b>x</b>"))
        self.assertNotIn("</script><b>", found.group(1))

    def test_member_only_topics_have_no_structured_data(self):
        """A topic in a group that only members read has no structured data, even when its author views it."""
        error = Category.objects.get(slug="gcd-error")
        topic = self.make_topic("Report", error, self.author)
        self.client.force_login(self.author)
        self.assertNotContains(self.client.get(topic.get_absolute_url()), "application/ld+json")


@override_settings(FORUM_EMAIL_ADDRESS="forum@comics.org", SITE_URL="https://www.comics.org/")
class DigestTests(ForumTestCase):
    """Weekly email summaries of a group, and the email mode chosen on the group page."""

    def setUp(self):
        """Give other an email address."""
        super().setUp()
        self.other.email = "other@example.com"
        self.other.save()

    def test_weekly_members_get_no_single_emails(self):
        """A member who chose the weekly summary gets no email for each new post."""
        GroupEmailSubscription.objects.create(user=self.other, category=self.main, mode="weekly")
        gateway.queue_post(Post.objects.create(
            discussion=self.discussion, author=self.author, content="Reply", created_by=self.author,
            updated_by=self.author, ip_address="127.0.0.1"))
        self.assertFalse(OutgoingEmail.objects.exists())

    def test_summary_is_sent_once_a_week_with_active_topics(self):
        """A summary due after a week lists active topics with new post counts; the next run sends none."""
        subscription = GroupEmailSubscription.objects.create(user=self.other, category=self.main, mode="weekly")
        GroupEmailSubscription.objects.filter(pk=subscription.pk).update(
            created_at=timezone.now() - timedelta(days=8))
        self.assertEqual(gateway.send_digests(), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "[gcd-main] Weekly summary")
        self.assertIn("A forum topic (new topic): 1 new post", message.body)
        self.assertIn("List-Unsubscribe", message.extra_headers)
        self.assertEqual(gateway.send_digests(), 0)

    def test_group_page_sets_the_email_mode(self):
        """The group page sets the email mode to weekly or each post; "off" deletes the subscription."""
        self.client.force_login(self.other)
        url = reverse("forum:group-email", args=[self.main.slug])
        self.client.post(url, {"mode": "weekly"})
        self.assertEqual(GroupEmailSubscription.objects.get().mode, "weekly")
        self.client.post(url, {"mode": "each"})
        self.assertEqual(GroupEmailSubscription.objects.get().mode, "each")
        self.client.post(url, {"mode": "off"})
        self.assertFalse(GroupEmailSubscription.objects.exists())
