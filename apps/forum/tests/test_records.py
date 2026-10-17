from django.template import Context, Template
from django.test import RequestFactory, override_settings
from django.urls import reverse

from apps.forum.models import Category, Discussion, DiscussionRecord
from apps.forum.records import parse_record_link

from .base import ForumTestCase


class RecordLinkTests(ForumTestCase):
    """GCD records linked to topics: parsing their links, previews, record pages and the forum button."""

    def setUp(self):
        """Create a publisher and the comics.org link to its page."""
        super().setUp()
        self.publisher = self.make_publisher()
        self.link = f"https://www.comics.org/publisher/{self.publisher.pk}/"

    def test_page_links_and_paths_resolve_to_records(self):
        """A record page's link or path gives its record; subpages, unknown ids and other text give None."""
        self.assertEqual(parse_record_link(self.link), ("publisher", self.publisher))
        self.assertEqual(parse_record_link(f"/publisher/{self.publisher.pk}"), ("publisher", self.publisher))
        self.assertIsNone(parse_record_link(f"/publisher/{self.publisher.pk}/brands/"))
        self.assertIsNone(parse_record_link("/publisher/999999999/"))
        self.assertIsNone(parse_record_link("not a link"))

    def test_deleted_record_is_not_linked(self):
        """The link of a deleted publisher gives no record."""
        self.publisher.deleted = True
        self.publisher.save()
        self.assertIsNone(parse_record_link(self.link))

    def test_topic_links_the_records_linked_in_the_message_once_each(self):
        """A new topic is linked once to each GCD record its message links to, even when linked twice."""
        second = self.make_publisher("Second publisher")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "Two publishers",
            "content": f"Same company? [First]({self.link}), https://www.comics.org/publisher/{second.pk}/ "
                       f"and {self.link} again; not https://example.com/publisher/{second.pk}/",
        })
        self.assertEqual(response.status_code, 302)
        topic = Discussion.objects.get(title="Two publishers")
        self.assertEqual(sorted(topic.records.values_list("object_id", flat=True)),
                         sorted([self.publisher.pk, second.pk]))

    def test_new_topic_shows_the_records_linked_in_the_message(self):
        """The record preview of a message shows a card of the linked publisher, opening in a new tab."""
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record-preview"), {"content": f"See {self.link}"})
        self.assertContains(response, "GCD records in your message")
        self.assertContains(response, f'target="_blank" rel="noopener">{self.publisher}</a>')

    def test_record_page_lists_topics_from_every_group(self):
        """The forum page of a record lists the topics linked to it in gcd-main and in gcd-tech."""
        tech = Category.objects.get(slug="gcd-tech")
        topic = self.make_topic("Tech about it", tech, self.author)
        for discussion in (self.discussion, topic):
            self._link(discussion)
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record", args=["publisher", self.publisher.pk]))
        self.assertContains(response, self.discussion.title)
        self.assertContains(response, "Tech about it")

    def test_record_page_count_respects_group_access(self):
        """The forum button of a GCD record page counts only the linked topics the user can read."""
        editor = Category.objects.get(slug="gcd-editor")
        self._link(self.discussion)
        self._link(self.make_topic("Hidden", editor, self.author))
        request = RequestFactory().get("/")
        template = Template("{% load forum_tags %}{% record_discussions 'publisher' record %}")
        rendered = template.render(Context({"user": self.other, "record": self.publisher, "request": request}))
        self.assertIn("Forum discussions (1)", rendered)
        self.assertIn(reverse("forum:record", args=["publisher", self.publisher.pk]), rendered)

    @override_settings(ROOT_URLCONF="apps.forum.tests.urls_without_forum")
    def test_record_pages_where_the_forum_is_not_mounted_show_no_button(self):
        """Without the forum's URLs, as with NO_OI or on my.comics.org, record pages show no forum button."""
        template = Template("{% load forum_tags %}{% record_discussions 'publisher' record %}")
        rendered = template.render(Context({"user": self.other, "record": self.publisher}))
        self.assertNotIn("Forum discussions", rendered)

    def test_record_page_offers_an_error_report_with_the_record(self):
        """Record pages offer an error report: a topic form preset with gcd-error and the record's link."""
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
        """For a visitor the button counts public topics only; a type that topics cannot link to has none."""
        from django.contrib.auth.models import AnonymousUser

        Category.objects.filter(pk=self.main.pk).update(read_access=Category.Access.PUBLIC)
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
        """A new topic opened from a record page starts with a link to the record in its message."""
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:discussion-create"),
                                   {"record": f"publisher:{self.publisher.pk}"})
        self.assertContains(response, f"/publisher/{self.publisher.pk}/")

    def test_preview_shows_found_and_invalid_links(self):
        """Previewing picked records lists the publisher to link and flags "nonsense" as not a record page."""
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record-preview"),
                                   {"records": f"{self.link}\nnonsense"})
        self.assertContains(response, "The topic will be linked to:")
        self.assertContains(response, str(self.publisher))
        self.assertContains(response, "Not a GCD record page: nonsense")

    def test_each_picked_record_shows_once(self):
        """A record picked twice shows once in the preview."""
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record-preview"), {"records": f"{self.link}\n{self.link}\n"})
        self.assertContains(response, f"/publisher/{self.publisher.pk}/", count=1)

    def test_only_author_or_staff_unlink_a_record(self):
        """Another user gets 403 unlinking a record from the topic; its author unlinks it."""
        link = self._link(self.discussion)
        url = reverse("forum:record-remove", args=[self.discussion.slug, link.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(DiscussionRecord.objects.filter(pk=link.pk).exists())

    def _link(self, discussion):
        """Link the topic to the publisher, as author; return the link."""
        from apps.forum.records import record_content_type

        return DiscussionRecord.objects.create(
            discussion=discussion, content_type=record_content_type("publisher"),
            object_id=self.publisher.pk, created_by=self.author)
