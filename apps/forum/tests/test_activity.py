from django.urls import reverse

from apps.forum.models import Category, Notification, TopicSubscription

from .base import ForumTestCase


class FollowAndNotifyTests(ForumTestCase):
    def reply(self, user, discussion=None, content="A reply"):
        self.client.force_login(user)
        discussion = discussion or self.discussion
        return self.client.post(reverse("forum:reply", args=[discussion.slug]), {"content": content})

    def test_creating_and_replying_follow_the_topic(self):
        self.client.force_login(self.other)
        self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Followed", "content": "Text"})
        self.assertTrue(TopicSubscription.objects.filter(user=self.other, discussion__title="Followed").exists())
        self.reply(self.other)
        self.assertTrue(TopicSubscription.objects.filter(user=self.other, discussion=self.discussion).exists())

    def test_reply_notifies_followers_but_not_its_author(self):
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.reply(self.other)
        self.assertEqual(Notification.objects.filter(user=self.author).count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.other).exists())

    def test_followers_who_lost_access_are_not_notified(self):
        editor = Category.objects.get(slug="gcd-editor")
        editor.members.add(self.author)
        topic = self.make_topic("Editors", editor, self.author)
        TopicSubscription.objects.create(user=self.other, discussion=topic)
        self.reply(self.author, topic)
        self.assertFalse(Notification.objects.filter(user=self.other).exists())

    def test_unfollow_stops_notifications(self):
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.author)
        self.client.post(reverse("forum:discussion-follow", args=[self.discussion.slug]))
        self.assertFalse(TopicSubscription.objects.filter(user=self.author, discussion=self.discussion).exists())
        self.reply(self.other)
        self.assertFalse(Notification.objects.filter(user=self.author).exists())

    def test_reading_the_topic_marks_its_notifications_read(self):
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.reply(self.other)
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse("forum:notifications")), "other replied in")
        self.client.get(self.discussion.get_absolute_url())
        self.assertFalse(Notification.objects.filter(user=self.author, read_at=None).exists())

    def test_following_feed_lists_followed_topics_only(self):
        self.make_topic("Not followed", self.main, self.other)
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.author)
        response = self.client.get(reverse("forum:index"), {"feed": "following"})
        self.assertContains(response, self.discussion.title)
        self.assertNotContains(response, "Not followed")


class UnreadTests(ForumTestCase):
    def test_new_replies_since_last_visit_are_counted_and_linked(self):
        self.client.force_login(self.author)
        self.client.get(self.discussion.get_absolute_url())
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "First new"})
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Second new"})
        first_new = self.discussion.posts.order_by("pk")[1]
        self.client.force_login(self.author)
        response = self.client.get(reverse("forum:index"))
        self.assertContains(response, "2 new")
        self.assertContains(response, f"#post-{first_new.pk}")
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, "Go to the first unread post")
        response = self.client.get(reverse("forum:index"))
        self.assertNotContains(response, "2 new")

    def test_own_replies_are_never_unread(self):
        self.client.force_login(self.author)
        self.client.get(self.discussion.get_absolute_url())
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Mine"})
        self.assertNotContains(self.client.get(reverse("forum:index")), " new</a>")
