from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.forum import mail as gateway
from apps.forum.models import Discussion, Notification, OutgoingEmail, Post, TopicSubscription

from .base import ForumTestCase
from .test_mail import raw_email


@override_settings(FORUM_REVIEW_FIRST_POSTS=True, FORUM_EMAIL_ADDRESS="forum@comics.org",
                   SITE_URL="https://www.comics.org/")
class ReviewTests(ForumTestCase):
    """The first post of an account without approved changes waits for a moderator of the group."""

    def setUp(self):
        """Create a moderator of gcd-main and newcomer, a user with an email address and no posts."""
        super().setUp()
        self.moderator = get_user_model().objects.create_user("coordinator", password="x")
        self.main.moderators.add(self.moderator)
        self.newcomer = get_user_model().objects.create_user("newcomer", password="x", email="new@example.com")

    def reply(self, user, content):
        """Post this reply to the topic as the user; return the response."""
        self.client.force_login(user)
        return self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": content})

    def test_first_reply_waits_for_a_moderator_then_reaches_the_followers(self):
        """A new member's first reply is hidden and not emailed until the notified moderator publishes it.

        Then its email to the followers is queued, and the member's next replies appear at once.
        """
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.author.email = "author@example.com"
        self.author.save()
        response = self.reply(self.newcomer, "Hello, I found an error.")
        self.assertRedirects(response, self.discussion.get_absolute_url(), fetch_redirect_response=False)
        held = Post.all_objects.get(author=self.newcomer)
        self.assertTrue(held.awaiting_review)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.discussion.get_absolute_url()), "I found an error")
        self.assertFalse(OutgoingEmail.objects.filter(post=held).exists())
        self.assertTrue(Notification.objects.filter(user=self.moderator, post=held, kind="review").exists())

        self.client.force_login(self.moderator)
        self.assertContains(self.client.get(reverse("forum:notifications")), "awaits your review")
        self.assertContains(self.client.get(reverse("forum:moderation")), "I found an error")
        self.client.post(reverse("forum:post-review", args=[held.pk]), {"action": "approve"})
        self.assertEqual(self.discussion.posts.filter(author=self.newcomer).count(), 1)
        self.assertTrue(OutgoingEmail.objects.filter(post=held, user=self.author).exists())
        self.assertEqual(Discussion.objects.get(pk=self.discussion.pk).post_count, 2)
        # Once a post is published, the next ones appear at once.
        self.reply(self.newcomer, "One more thing.")
        self.assertFalse(Post.all_objects.get(content="One more thing.").awaiting_review)

    def test_new_topic_of_a_new_member_is_hidden_until_published_and_can_be_rejected(self):
        """A new member's topic is hidden and its page a 404 until reviewed; rejecting its post removes it."""
        self.client.force_login(self.newcomer)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Buy cheap comics", "content": "Spam"})
        self.assertRedirects(response, self.main.get_absolute_url(), fetch_redirect_response=False)
        topic = Discussion.all_objects.get(title="Buy cheap comics")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("forum:index")), "Buy cheap comics")
        self.assertEqual(self.client.get(topic.get_absolute_url()).status_code, 404)

        post = Post.all_objects.get(discussion=topic)
        self.client.force_login(self.moderator)
        self.assertContains(self.client.get(reverse("forum:moderation")), "New topic: Buy cheap comics")
        self.client.post(reverse("forum:post-review", args=[post.pk]), {"action": "reject"})
        topic.refresh_from_db()
        self.assertTrue(topic.is_deleted)

    def test_only_the_groups_moderators_review(self):
        """A user who does not moderate the group gets 403 when publishing a held post."""
        self.reply(self.newcomer, "Hello")
        held = Post.all_objects.get(author=self.newcomer)
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:post-review", args=[held.pk]), {"action": "approve"})
        self.assertEqual(response.status_code, 403)

    def test_members_with_posts_moderators_and_indexers_post_directly(self):
        """A member with an earlier post and a moderator of the group post without review."""
        self.reply(self.author, "The author already posted.")
        self.reply(self.moderator, "A moderator.")
        self.assertFalse(Post.all_objects.filter(awaiting_review=True).exists())

    def test_first_post_by_email_waits_too(self):
        """A new member's first reply by email waits for a moderator too, as its IncomingEmail record says."""
        record = gateway.process_message(raw_email(
            "new@example.com", gateway.reply_address(self.newcomer, self.discussion), "Re: topic", "By email"))
        self.assertEqual(record.reason, "awaiting review by a moderator")
        self.assertTrue(record.post.awaiting_review)

    def test_approval_leaves_the_read_marks_alone(self):
        """Approving a held reply does not lower anyone's read mark: the posts a reader read after it stay
        read, and the reader hears of the approved one from the follow notification."""
        from apps.forum.models import TopicRead

        self.reply(self.newcomer, "Held for review.")
        held = Post.all_objects.get(author=self.newcomer)
        later = Post.objects.create(discussion=self.discussion, author=self.other, content="Later",
                                    created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
        TopicRead.objects.create(user=self.author, discussion=self.discussion, last_read_post_id=later.pk)
        self.client.force_login(self.moderator)
        self.client.post(reverse("forum:post-review", args=[held.pk]), {"action": "approve"})
        self.assertEqual(TopicRead.objects.get(user=self.author).last_read_post_id, later.pk)

    def test_a_held_reply_sent_by_htmx_is_marked_as_held(self):
        """The htmx answer to a held reply carries data-held-for-review, so the page says it waits for a
        moderator instead of saying it was posted."""
        self.client.force_login(self.newcomer)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "Held reply"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "data-held-for-review")
