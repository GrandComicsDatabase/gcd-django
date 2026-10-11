import datetime

from django.urls import reverse
from django.utils import timezone

from apps.forum.models import Category, Discussion, Post, Suspension

from .base import ForumTestCase


class ModeratorTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model

        self.coordinator = get_user_model().objects.create_user("coordinator", password="test-password")
        self.main.moderators.add(self.coordinator)
        self.url = reverse("forum:discussion-moderate", args=[self.discussion.slug])

    def test_moderator_pins_and_closes_a_topic(self):
        self.client.force_login(self.coordinator)
        self.assertEqual(self.client.post(self.url, {"action": "pin"}).status_code, 302)
        self.assertEqual(self.client.post(self.url, {"action": "close"}).status_code, 302)
        self.discussion.refresh_from_db()
        self.assertTrue(self.discussion.is_pinned)
        self.assertTrue(self.discussion.is_locked)
        self.client.post(self.url, {"action": "reopen"})
        self.discussion.refresh_from_db()
        self.assertFalse(self.discussion.is_locked)

    def test_author_cannot_pin_their_own_topic(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(self.url, {"action": "pin"}).status_code, 403)
        self.discussion.refresh_from_db()
        self.assertFalse(self.discussion.is_pinned)

    def test_moderator_of_another_group_has_no_power_here(self):
        tech = Category.objects.get(slug="gcd-tech")
        self.main.moderators.remove(self.coordinator)
        tech.moderators.add(self.coordinator)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.client.post(self.url, {"action": "pin"}).status_code, 403)
        response = self.client.post(reverse("forum:post-delete", args=[self.post.pk]))
        self.assertEqual(response.status_code, 403)

    def test_moderator_removes_and_moves_other_users_content(self):
        self.client.force_login(self.coordinator)
        response = self.client.post(reverse("forum:post-delete", args=[self.post.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.all_objects.get(pk=self.post.pk).is_deleted)
        policy = Category.objects.get(slug="gcd-policy")
        response = self.client.post(reverse("forum:discussion-move", args=[self.discussion.slug]),
                                    {"category": policy.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Discussion.objects.get(pk=self.discussion.pk).category, policy)

    def test_topic_page_shows_moderation_buttons_to_moderators_only(self):
        self.client.force_login(self.coordinator)
        self.assertContains(self.client.get(self.discussion.get_absolute_url()), 'value="pin"')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.discussion.get_absolute_url()), 'value="pin"')


class SuspensionTests(ForumTestCase):
    def suspend(self, category=None, until=None):
        return Suspension.objects.create(user=self.other, category=category, until=until,
                                         reason="Repeated off-topic posts", created_by=self.author)

    def reply(self):
        return self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hi"})

    def test_suspended_user_cannot_reply_or_start_topics_in_the_group(self):
        self.suspend(self.main)
        self.client.force_login(self.other)
        self.assertEqual(self.reply().status_code, 403)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Still here", "content": "Text"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Discussion.objects.filter(title="Still here").exists())
        self.assertContains(self.client.get(self.discussion.get_absolute_url()), self.discussion.title)

    def test_group_suspension_leaves_other_groups_open(self):
        self.suspend(self.main)
        tech = Category.objects.get(slug="gcd-tech")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": tech.pk, "title": "Tech topic", "content": "Text"})
        self.assertEqual(response.status_code, 302)

    def test_suspension_without_group_covers_every_group(self):
        self.suspend()
        self.assertFalse(Category.objects.get(slug="gcd-tech").can_post(self.other))
        self.assertFalse(self.main.can_post(self.other))

    def test_expired_suspension_no_longer_applies(self):
        self.suspend(self.main, until=timezone.now() - datetime.timedelta(days=1))
        self.client.force_login(self.other)
        self.assertEqual(self.reply().status_code, 302)
