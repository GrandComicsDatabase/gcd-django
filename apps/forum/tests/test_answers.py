from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.forum.models import Category, Discussion, Post

from .base import ForumTestCase


class AcceptedAnswerTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.reply = Post.objects.create(
            discussion=self.discussion, author=self.other, content="The answer",
            created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
        self.url = reverse("forum:post-answer", args=[self.reply.pk])

    def test_topic_author_accepts_and_unmarks_an_answer(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.discussion.refresh_from_db()
        self.assertEqual(self.discussion.answer, self.reply)
        self.assertEqual(self.discussion.status, Discussion.Status.RESOLVED)
        self.assertContains(self.client.get(self.discussion.get_absolute_url()), "Accepted answer")
        self.client.post(self.url)
        self.discussion.refresh_from_db()
        self.assertIsNone(self.discussion.answer)
        self.assertEqual(self.discussion.status, Discussion.Status.OPEN)

    def test_other_users_cannot_accept(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_group_moderator_can_accept(self):
        moderator = get_user_model().objects.create_user("coordinator", password="x")
        self.main.moderators.add(moderator)
        self.client.force_login(moderator)
        self.assertEqual(self.client.post(self.url).status_code, 302)

    def test_question_itself_cannot_be_the_answer(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:post-answer", args=[self.post.pk]))
        self.assertEqual(response.status_code, 403)


class DuplicateTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.moderator = get_user_model().objects.create_user("coordinator", password="x")
        self.main.moderators.add(self.moderator)
        self.copy = self.make_topic("Same question again", self.main, self.other)
        self.url = reverse("forum:discussion-duplicate", args=[self.copy.slug])

    def test_moderator_closes_a_duplicate_with_a_link_to_the_original(self):
        self.client.force_login(self.moderator)
        link = f"https://www.comics.org{self.discussion.get_absolute_url()}"
        self.assertEqual(self.client.post(self.url, {"original": link}).status_code, 302)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.duplicate_of, self.discussion)
        self.assertTrue(self.copy.is_locked)
        response = self.client.get(self.copy.get_absolute_url())
        self.assertContains(response, "Closed as a duplicate of")
        self.assertContains(response, self.discussion.get_absolute_url())

    def test_original_must_be_another_readable_topic(self):
        editor = Category.objects.get(slug="gcd-editor")
        hidden = self.make_topic("Hidden", editor, self.author)
        self.client.force_login(self.moderator)
        for original in (self.copy.get_absolute_url(), hidden.get_absolute_url(), "/series/1/", "nonsense"):
            self.client.post(self.url, {"original": original})
            self.copy.refresh_from_db()
            self.assertIsNone(self.copy.duplicate_of, original)

    def test_only_moderators_close_duplicates(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url, {"original": self.discussion.get_absolute_url()})
        self.assertEqual(response.status_code, 403)
