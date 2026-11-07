from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.forum.models import Category, Post, Report

from .base import ForumTestCase


class ReportQueueTests(ForumTestCase):
    """The moderators' queue of reported posts and topics, and who may handle it."""

    def setUp(self):
        """Have author report other's reply "Spam spam", and make a moderator of gcd-main."""
        super().setUp()
        self.reply = Post.objects.create(discussion=self.discussion, author=self.other, content="Spam spam",
                                         created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
        self.client.force_login(self.author)
        self.client.post(reverse("forum:report", args=["post", self.reply.pk]), {"reason": "Spam"})
        self.report = Report.objects.get()
        self.moderator = self.make_moderator(self.main)

    def make_moderator(self, category):
        """Create a moderator of the group, named mod-<group slug>; return them."""
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(f"mod-{category.slug}", password="x")
        category.moderators.add(user)
        return user

    def test_group_moderator_sees_and_removes_reported_content(self):
        """The group's moderator sees the reported post and removes it; the report says they actioned it."""
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("forum:moderation"))
        self.assertContains(response, "Spam spam")
        self.assertContains(response, "Reports to review")
        self.client.post(reverse("forum:report-resolve", args=[self.report.pk]), {"action": "remove"})
        self.report.refresh_from_db()
        self.assertEqual((self.report.status, self.report.reviewed_by), (Report.Status.ACTIONED, self.moderator))
        self.assertTrue(Post.all_objects.get(pk=self.reply.pk).is_deleted)

    def test_dismissing_keeps_the_content(self):
        """Dismissing a report marks it dismissed and leaves the post in place."""
        self.client.force_login(self.moderator)
        self.client.post(reverse("forum:report-resolve", args=[self.report.pk]), {"action": "dismiss"})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.DISMISSED)
        self.assertFalse(Post.all_objects.get(pk=self.reply.pk).is_deleted)

    def test_a_second_report_says_so_and_reopens_a_handled_one(self):
        """Reporting again while the report is open says it is already there; after a dismissal it opens again."""
        url = reverse("forum:report", args=["post", self.reply.pk])
        response = self.client.post(url, {"reason": "Still spam"}, follow=True)
        self.assertContains(response, "You have already reported this")
        self.report.refresh_from_db()
        self.assertEqual((self.report.reason, self.report.status), ("Spam", Report.Status.OPEN))
        self.client.force_login(self.moderator)
        self.client.post(reverse("forum:report-resolve", args=[self.report.pk]), {"action": "dismiss"})
        self.client.force_login(self.author)
        response = self.client.post(url, {"reason": "Now it is abuse"}, follow=True)
        self.assertContains(response, "Your report was sent to the moderators")
        self.report.refresh_from_db()
        self.assertEqual((self.report.reason, self.report.status, self.report.reviewed_by),
                         ("Now it is abuse", Report.Status.OPEN, None))

    def test_moderators_of_other_groups_and_users_have_no_queue(self):
        """A gcd-tech moderator cannot see or resolve the report, and the queue is a 404 for plain users."""
        tech = self.make_moderator(Category.objects.get(slug="gcd-tech"))
        self.client.force_login(tech)
        self.assertNotContains(self.client.get(reverse("forum:moderation")), "Spam spam")
        response = self.client.post(reverse("forum:report-resolve", args=[self.report.pk]), {"action": "remove"})
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("forum:moderation")).status_code, 404)

    def test_topic_reports_are_listed_too(self):
        """A report about a topic, not a post, is listed in the moderator's queue too."""
        Report.objects.create(reporter=self.other, content_type=ContentType.objects.get_for_model(self.discussion),
                              object_id=self.discussion.pk, reason="Off topic")
        self.client.force_login(self.moderator)
        self.assertContains(self.client.get(reverse("forum:moderation")), "Off topic")

    def test_an_author_removing_a_reported_post_leaves_the_report_to_the_moderators(self):
        """The author of a reported post removes it: the report stays open in the queue, marked removed."""
        self.client.force_login(self.other)
        self.client.post(reverse("forum:post-delete", args=[self.reply.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.OPEN)
        self.client.force_login(self.moderator)
        self.assertContains(self.client.get(reverse("forum:moderation")), "(removed)")

    def test_removing_a_reported_topic_closes_the_reports_of_its_posts(self):
        """A moderator removing a topic from its report closes the reports about its posts too."""
        topic_report = Report.objects.create(
            reporter=self.other, content_type=ContentType.objects.get_for_model(self.discussion),
            object_id=self.discussion.pk, reason="Off topic")
        self.client.force_login(self.moderator)
        self.client.post(reverse("forum:report-resolve", args=[topic_report.pk]), {"action": "remove"})
        self.report.refresh_from_db()
        self.assertEqual((self.report.status, self.report.reviewed_by), (Report.Status.ACTIONED, self.moderator))

    def test_only_moderators_learn_whether_a_report_was_handled(self):
        """A user who is not a moderator gets 403 for a handled report as for an open one."""
        self.client.force_login(self.moderator)
        self.client.post(reverse("forum:report-resolve", args=[self.report.pk]), {"action": "dismiss"})
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:report-resolve", args=[self.report.pk]), {"action": "dismiss"})
        self.assertEqual(response.status_code, 403)

    def test_the_queue_costs_the_same_queries_for_more_reports(self):
        """The authors, topics and groups of the reported content are loaded for all reports at once."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.moderator)
        with CaptureQueriesContext(connection) as one:
            self.client.get(reverse("forum:moderation"))
        for number in range(3):
            post = Post.objects.create(discussion=self.discussion, author=self.author, content=f"Spam {number}",
                                       created_by=self.author, updated_by=self.author, ip_address="127.0.0.1")
            Report.objects.create(reporter=self.other, content_type=ContentType.objects.get_for_model(post),
                                  object_id=post.pk, reason="Spam")
        with CaptureQueriesContext(connection) as four:
            response = self.client.get(reverse("forum:moderation"))
        self.assertContains(response, "Spam 2")
        self.assertEqual(len(four), len(one))
