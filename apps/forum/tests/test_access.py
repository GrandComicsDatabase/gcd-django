from django.test import Client
from django.urls import reverse

from apps.forum.models import Category, Discussion

from .base import ForumTestCase


class VisitorTests(ForumTestCase):
    """Public lists can be read without an account; writing needs one."""

    def test_visitor_reads_public_lists(self):
        for url in (reverse("forum:index"), self.main.get_absolute_url(),
                    self.discussion.get_absolute_url()):
            self.assertContains(self.client.get(url), self.discussion.title)
        response = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(response, self.post.content)
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "quick-reply-form")

    def test_visitor_cannot_write(self):
        for url, data in ((reverse("forum:reply", args=[self.discussion.slug]), {"content": "x"}),
                          (reverse("forum:post-vote", args=[self.post.pk]), {}),
                          (reverse("forum:discussion-create"), {})):
            response = self.client.post(url, data)
            self.assertContains(response, "Sign in", status_code=403)
        self.assertEqual(self.discussion.posts.count(), 1)
        response = self.client.get(reverse("forum:post-edit", args=[self.post.pk]))
        self.assertContains(response, "Sign in", status_code=403)

    def test_visitor_does_not_see_member_only_lists(self):
        editor = Category.objects.get(slug="gcd-editor")
        error = Category.objects.get(slug="gcd-error")
        hidden = self.make_topic("Editors only", editor, self.author)
        report = self.make_topic("An error report", error, self.author)
        for topic in (hidden, report):
            self.assertEqual(self.client.get(topic.get_absolute_url()).status_code, 404)
        response = self.client.get(reverse("forum:index"))
        self.assertNotContains(response, "Editors only")
        self.assertNotContains(response, "An error report")
        self.assertNotContains(response, "gcd-editor")

    def test_csrf_required_for_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.other)
        response = client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "No token"})
        self.assertEqual(response.status_code, 403)


class GroupAccessTests(ForumTestCase):
    """Read and post access per group, as in the Email Lists FAQ."""

    def test_faq_groups_are_seeded_without_contact(self):
        slugs = set(Category.objects.values_list("slug", flat=True))
        self.assertIn("gcd-italia", slugs)
        self.assertEqual(len(slugs), 16)
        self.assertNotIn("gcd-contact", slugs)

    def test_board_is_readable_by_all_and_writable_by_members(self):
        board = Category.objects.get(slug="gcd-board")
        topic = self.make_topic("Board vote", board, self.author)
        self.client.force_login(self.other)
        response = self.client.get(topic.get_absolute_url())
        self.assertContains(response, "Board vote")
        self.assertContains(response, "Only members of gcd-board can reply")
        response = self.client.post(reverse("forum:reply", args=[topic.slug]), {"content": "Me too"})
        self.assertEqual(response.status_code, 403)
        board.members.add(self.other)
        response = self.client.post(reverse("forum:reply", args=[topic.slug]), {"content": "Me too"})
        self.assertEqual(response.status_code, 302)

    def test_error_reports_are_seen_by_reporter_and_members_only(self):
        error = Category.objects.get(slug="gcd-error")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": error.pk, "title": "Wrong date", "content": "The date is wrong."})
        self.assertEqual(response.status_code, 302)
        report = Discussion.objects.get(title="Wrong date")
        self.assertEqual(self.client.get(report.get_absolute_url()).status_code, 200)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(report.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(error.get_absolute_url()), "Wrong date")
        error.members.add(self.author)
        self.assertEqual(self.client.get(report.get_absolute_url()).status_code, 200)

    def test_editor_group_is_hidden_from_non_members(self):
        editor = Category.objects.get(slug="gcd-editor")
        topic = self.make_topic("Editors only", editor, self.author)
        editor.members.add(self.author)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(editor.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(topic.get_absolute_url()).status_code, 404)
        response = self.client.get(reverse("forum:index"), {"q": "Editors only"})
        self.assertNotContains(response, topic.get_absolute_url())
        for route in ("post-vote", "post-delete", "post-edit"):
            post = topic.posts.get()
            self.assertEqual(self.client.post(reverse(f"forum:{route}", args=[post.pk])).status_code, 404)

    def test_forged_group_is_rejected_by_create_form(self):
        editor = Category.objects.get(slug="gcd-editor")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": editor.pk, "title": "Forbidden topic", "content": "No access"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Discussion.objects.filter(title="Forbidden topic").exists())
