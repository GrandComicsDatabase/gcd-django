from django.template import Context, Template
from django.test import RequestFactory
from django.urls import reverse

from apps.forum.models import Category, Discussion, DiscussionRecord
from apps.forum.records import parse_record_link

from .base import ForumTestCase


class RecordLinkTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = self.make_publisher()
        self.link = f"https://www.comics.org/publisher/{self.publisher.pk}/"

    def test_page_links_and_paths_resolve_to_records(self):
        self.assertEqual(parse_record_link(self.link), ("publisher", self.publisher))
        self.assertEqual(parse_record_link(f"/publisher/{self.publisher.pk}"), ("publisher", self.publisher))
        self.assertIsNone(parse_record_link(f"/publisher/{self.publisher.pk}/brands/"))
        self.assertIsNone(parse_record_link("/publisher/999999999/"))
        self.assertIsNone(parse_record_link("not a link"))

    def test_deleted_record_is_not_linked(self):
        self.publisher.deleted = True
        self.publisher.save()
        self.assertIsNone(parse_record_link(self.link))

    def test_topic_links_many_records_once_each(self):
        second = self.make_publisher("Second publisher")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Two publishers", "content": "Same company?",
            "records": f"{self.link}\n/publisher/{second.pk}/\n{self.link}",
        })
        self.assertEqual(response.status_code, 302)
        topic = Discussion.objects.get(title="Two publishers")
        self.assertEqual(sorted(topic.records.values_list("object_id", flat=True)),
                         sorted([self.publisher.pk, second.pk]))

    def test_invalid_link_blocks_the_topic(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Bad link", "content": "Text",
            "records": "https://example.com/nothing/",
        })
        self.assertContains(response, "Not a link to a GCD record page")
        self.assertFalse(Discussion.objects.filter(title="Bad link").exists())

    def test_record_page_lists_topics_from_every_group(self):
        tech = Category.objects.get(slug="gcd-tech")
        topic = self.make_topic("Tech about it", tech, self.author)
        for discussion in (self.discussion, topic):
            self._link(discussion)
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record", args=["publisher", self.publisher.pk]))
        self.assertContains(response, self.discussion.title)
        self.assertContains(response, "Tech about it")

    def test_record_page_count_respects_group_access(self):
        editor = Category.objects.get(slug="gcd-editor")
        self._link(self.discussion)
        self._link(self.make_topic("Hidden", editor, self.author))
        request = RequestFactory().get("/")
        template = Template("{% load forum_tags %}{% record_discussions 'publisher' record %}")
        rendered = template.render(Context({"user": self.other, "record": self.publisher, "request": request}))
        self.assertIn("Forum discussions (1)", rendered)
        self.assertIn(reverse("forum:record", args=["publisher", self.publisher.pk]), rendered)

    def test_record_page_offers_an_error_report_with_the_record(self):
        template = Template("{% load forum_tags %}{% record_discussions 'publisher' record %}")
        rendered = template.render(Context({"user": self.other, "record": self.publisher}))
        self.assertIn(f"?category=gcd-error&amp;record=publisher:{self.publisher.pk}", rendered)
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:discussion-create"),
                                   {"category": "gcd-error", "record": f"publisher:{self.publisher.pk}"})
        self.assertContains(response, f"/publisher/{self.publisher.pk}/")
        error = Category.objects.get(slug="gcd-error")
        self.assertEqual(response.context["form"].initial["category"], error.pk)

    def test_record_page_link_for_visitors_counts_public_topics(self):
        from django.contrib.auth.models import AnonymousUser

        self._link(self.discussion)
        self._link(self.make_topic("Hidden", Category.objects.get(slug="gcd-editor"), self.author))
        template = Template("{% load forum_tags %}{% record_discussions model_name record %}")
        rendered = template.render(Context({"user": AnonymousUser(), "record": self.publisher,
                                            "model_name": "publisher"}))
        self.assertIn("Forum discussions (1)", rendered)
        rendered = template.render(Context({"user": self.other, "record": self.publisher,
                                            "model_name": "cover"}))
        self.assertNotIn("Forum discussions", rendered)

    def test_new_topic_from_a_record_page_prefills_the_link(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:discussion-create"),
                                   {"record": f"publisher:{self.publisher.pk}"})
        self.assertContains(response, f"/publisher/{self.publisher.pk}/")

    def test_preview_shows_found_and_invalid_links(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record-preview"),
                                   {"records": f"{self.link}\nnonsense"})
        self.assertContains(response, str(self.publisher))
        self.assertContains(response, "Not a GCD record page: nonsense")

    def test_only_author_or_staff_unlink_a_record(self):
        link = self._link(self.discussion)
        url = reverse("forum:record-remove", args=[self.discussion.slug, link.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(DiscussionRecord.objects.filter(pk=link.pk).exists())

    def _link(self, discussion):
        from apps.forum.records import record_content_type

        return DiscussionRecord.objects.create(
            discussion=discussion, content_type=record_content_type("publisher"),
            object_id=self.publisher.pk, created_by=self.author)
