from django.urls import reverse

from apps.forum.models import Category, Notification, TopicSubscription

from .base import ForumTestCase


class FollowAndNotifyTests(ForumTestCase):
    """Following topics, the notifications of their replies and the Following feed."""

    def reply(self, user, discussion=None, content="A reply"):
        """Post a reply as the user, to the test topic unless another topic is given."""
        self.client.force_login(user)
        discussion = discussion or self.discussion
        return self.client.post(reverse("forum:reply", args=[discussion.slug]), {"content": content})

    def test_creating_and_replying_follow_the_topic(self):
        """Starting a topic or replying to one makes the user follow it."""
        self.client.force_login(self.other)
        self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Followed", "content": "Text"})
        self.assertTrue(TopicSubscription.objects.filter(user=self.other, discussion__title="Followed").exists())
        self.reply(self.other)
        self.assertTrue(TopicSubscription.objects.filter(user=self.other, discussion=self.discussion).exists())

    def test_reply_notifies_followers_but_not_its_author(self):
        """A reply notifies the followers of the topic, but not its own author."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.reply(self.other)
        self.assertEqual(Notification.objects.filter(user=self.author).count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.other).exists())

    def test_followers_who_lost_access_are_not_notified(self):
        """Followers who cannot read the topic are not notified of its replies."""
        editor = Category.objects.get(slug="gcd-editor")
        editor.members.add(self.author)
        topic = self.make_topic("Editors", editor, self.author)
        TopicSubscription.objects.create(user=self.other, discussion=topic)
        self.reply(self.author, topic)
        self.assertFalse(Notification.objects.filter(user=self.other).exists())

    def test_unfollow_stops_notifications(self):
        """Unfollowing a topic ends the subscription and the notifications of its replies."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-follow", args=[self.discussion.slug]), {"follow": "0"})
        self.assertFalse(TopicSubscription.objects.filter(user=self.author, discussion=self.discussion).exists())
        self.reply(self.other)
        self.assertFalse(Notification.objects.filter(user=self.author).exists())

    def test_reading_the_topic_marks_its_notifications_read(self):
        """The notifications page lists the reply, and opening the topic marks its notifications read."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.reply(self.other)
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse("forum:notifications")),
                            f"GCD user {self.other.pk} replied in")
        self.client.get(self.discussion.get_absolute_url())
        self.assertFalse(Notification.objects.filter(user=self.author, read_at=None).exists())

    def test_following_feed_lists_followed_topics_only(self):
        """The Following feed lists the topics the user follows and no others."""
        self.make_topic("Not followed", self.main, self.other)
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.author)
        response = self.client.get(reverse("forum:index"), {"feed": "following"})
        self.assertContains(response, self.discussion.title)
        self.assertNotContains(response, "Not followed")


class UnreadTests(ForumTestCase):
    """Unread replies: those posted by others since the user's last visit to the topic."""

    def test_new_replies_since_last_visit_are_counted_and_linked(self):
        """Replies since the last visit show as unread, with a link to the first, until the topic is read."""
        self.client.force_login(self.author)
        self.client.get(self.discussion.get_absolute_url())
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "First new"})
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Second new"})
        first_new = self.discussion.posts.order_by("pk")[1]
        self.client.force_login(self.author)
        response = self.client.get(reverse("forum:index"))
        self.assertContains(response, "2 unread")
        self.assertContains(response, f"#post-{first_new.pk}")
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, "Go to the first unread post")
        response = self.client.get(reverse("forum:index"))
        self.assertNotContains(response, "2 unread")

    def test_own_replies_are_never_unread(self):
        """The user's own replies never count as unread."""
        self.client.force_login(self.author)
        self.client.get(self.discussion.get_absolute_url())
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Mine"})
        self.assertTrue(self.discussion.posts.filter(author=self.author, content="Mine").exists())
        self.assertNotContains(self.client.get(reverse("forum:index")), " unread</a>")
