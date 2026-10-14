from django.db import connection
from django.template import Context, Template
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.forum.models import DiscussionRecord
from apps.forum.records import records_in_text, search_records
from apps.forum.templatetags.forum_tags import safe_markdown

from .base import ForumTestCase


class PreviewTests(ForumTestCase):
    """The Preview tab of the message box, and how safe_markdown renders quotes, tags, code and links."""

    def test_preview_renders_safe_markdown(self):
        """The preview renders **bold** as strong text and lets no <script> tag through."""
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:markdown-preview"),
                                    {"content": "**bold** <script>alert(1)</script>"})
        self.assertContains(response, "<strong>bold</strong>", html=True)
        self.assertNotContains(response, "<script>")

    def test_visitors_cannot_preview(self):
        """A visitor who is not signed in gets 403 from the preview."""
        self.assertEqual(self.client.post(reverse("forum:markdown-preview"), {"content": "x"}).status_code, 403)

    def test_quotes_become_blockquotes_and_tags_stay_text(self):
        """Lines starting with ">" become a blockquote, while tags, "&" and ">" inside a line stay text."""
        html = str(safe_markdown("@author wrote:\n> In 1954.\n> Not later.\n\n<b>Thanks</b> & x > y"))
        self.assertIn("<blockquote>", html)
        self.assertIn("In 1954.", html)
        self.assertNotIn("&gt; In 1954.", html)
        self.assertIn("&lt;b&gt;Thanks&lt;/b&gt; &amp; x &gt; y", html)

    def test_answers_between_quotes_stay_outside_them(self):
        """A line with fewer ">" ends the quote, as in email, so answers between quotes stay outside them."""
        self.assertHTMLEqual(str(safe_markdown("> question one\nanswer one\n> question two\nanswer two")),
                             "<blockquote><p>question one</p></blockquote><p>answer one</p>"
                             "<blockquote><p>question two</p></blockquote><p>answer two</p>")
        self.assertHTMLEqual(str(safe_markdown("> > old\n> newer\nmy answer")),
                             "<blockquote><blockquote><p>old</p></blockquote><p>newer</p></blockquote>"
                             "<p>my answer</p>")

    def test_code_link_titles_and_mail_links_render_as_written(self):
        """Inline code shows its text as written, a link keeps its title, and <https://...> becomes a link."""
        html = str(safe_markdown("`don't` `a < b && c` `<b>` `&lt;x&gt;`"))
        self.assertIn("<code>don&#x27;t</code>", html)
        self.assertIn("<code>a &lt; b &amp;&amp; c</code>", html)
        self.assertIn("<code>&lt;b&gt;</code>", html)
        self.assertIn("<code>&amp;lt;x&amp;gt;</code>", html)
        html = str(safe_markdown(
            '[GCD](https://www.comics.org/series/1/ "The series") and <https://www.comics.org/issue/2/>'))
        self.assertIn('href="https://www.comics.org/series/1/" title="The series"', html)
        self.assertIn('href="https://www.comics.org/issue/2/"', html)


class MessageBoxTests(ForumTestCase):
    """New topic, reply and edit share one message box; only new messages take files."""

    def assertMessageBox(self, response, files):
        """Assert the page has the message box, and its file input only when files is true."""
        self.assertContains(response, "data-editor")
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, "Link a GCD record")
        self.assertContains(response, reverse("forum:record-search"))
        if files:
            self.assertContains(response, 'data-max-files="5"')
            self.assertContains(response, 'accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"')
        else:
            self.assertNotContains(response, "data-file-input")

    def test_new_topic_reply_and_edit_use_the_same_box(self):
        """The new topic page, the topic page and the post edit page show the box; editing takes no files."""
        self.client.force_login(self.author)
        self.assertMessageBox(self.client.get(reverse("forum:discussion-create")), files=True)
        self.assertMessageBox(self.client.get(self.discussion.get_absolute_url()), files=True)
        self.assertMessageBox(self.client.get(reverse("forum:post-edit", args=[self.post.pk])), files=False)

    def test_box_shows_the_cards_of_the_linked_records(self):
        """The box shows cards of the first six linked records, opening in a new tab, and counts the rest."""
        publishers = [self.make_publisher(f"Publisher {number}") for number in range(7)]
        links = " ".join(f"https://www.comics.org/publisher/{publisher.pk}/" for publisher in publishers)
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record-preview"), {"content": links})
        self.assertContains(response, "GCD records in your message")
        self.assertContains(response, 'target="_blank"', count=6)
        self.assertContains(response, "and 1 more record")

    def test_a_reply_sent_back_stays_in_its_thread_with_readable_errors(self):
        """An empty answer to a reply returns 422, aimed at that reply and its thread, with red-700 errors."""
        from apps.forum.models import Post

        answer = Post.objects.create(discussion=self.discussion, author=self.other, parent=self.post,
                                     content="An answer", created_by=self.other, updated_by=self.other,
                                     ip_address="127.0.0.1")
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "   ", "parent": answer.pk}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, f'hx-target="#children-{self.post.pk}"', status_code=422)
        self.assertContains(response, f"Reply to GCD user {self.other.pk}", status_code=422)
        self.assertContains(response, 'class="errorlist text-red-700"', status_code=422)

    def test_a_form_sent_back_says_that_the_files_are_not_kept(self):
        """A new topic form sent back with an error says to attach the files again; a fresh form does not."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "With a scan", "content": "See the scan",
            "poll_question": "Which year?", "poll_options": "1972",
            "attachments": SimpleUploadedFile("scan.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")})
        self.assertContains(response, "Files are not kept when the form comes back with an error")
        self.assertNotContains(self.client.get(reverse("forum:discussion-create")), "Files are not kept")

    def test_a_closed_agenda_item_says_why_the_topic_is_not_published(self):
        """A new topic for an unknown agenda item comes back saying the item is closed or no longer exists."""
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "On the agenda", "content": "Text", "agenda_item": 999999})
        self.assertContains(response, "This agenda item is closed or no longer exists")

    def test_published_post_cards_stay_as_they_were(self):
        """The record cards of a published post keep their label and open in the same tab."""
        publisher = self.make_publisher()
        self.post.content = f"See https://www.comics.org/publisher/{publisher.pk}/"
        html = Template("{% load forum_tags %}{% record_cards post %}").render(Context({"post": self.post}))
        self.assertIn('aria-label="GCD records in this post"', html)
        self.assertNotIn("target=", html)


class RecordSearchTests(ForumTestCase):
    """Search of GCD records by name, to link them to a topic, and the view that lists the results."""

    def setUp(self):
        """Create two publishers, three Spider-Man series in English and Italian, and an issue #12."""
        super().setUp()
        from apps.gcd.models import Issue, Series
        from apps.stddata.models import Language

        self.publisher = self.make_publisher("Marvelous Comics")
        self.make_publisher("The Marvelous Group")
        english, _ = Language.objects.get_or_create(code="en", defaults={"name": "English"})
        italian, _ = Language.objects.get_or_create(code="it", defaults={"name": "Italian"})

        def series(name, sort_name, language, year, issues):
            """Create a series of Marvelous Comics that ends ten years after the year it begins."""
            return Series.objects.create(
                name=name, sort_name=sort_name, publisher=self.publisher, country=self.publisher.country,
                language=language, year_began=year, year_ended=year + 10, issue_count=issues)

        self.amazing = series("The Amazing Spider-Man", "Amazing Spider-Man", english, 1963, 441)
        self.spanish = series("Spiderman", "Spiderman", italian, 1983, 300)
        self.later = series("Amazing Spider-Man", "Amazing Spider-Man", english, 2018, 90)
        Issue.objects.create(series=self.amazing, number="12", sort_code=12)

    def names(self, *args, **kwargs):
        """Names of the records that search_records returns, in order."""
        return [record.name for record in search_records(*args, **kwargs)[0]]

    def test_names_starting_with_the_query_come_first(self):
        """A name starting with the query comes before one that only contains it; one letter finds nothing."""
        self.assertEqual(self.names("publisher", "marvelous"), ["Marvelous Comics", "The Marvelous Group"])
        self.assertEqual(self.names("publisher", "m"), [])

    def test_punctuation_and_leading_articles_do_not_matter(self):
        """Hyphens and a leading "The" do not matter: "amazing spiderman" finds both, more issues first."""
        self.assertEqual(self.names("series", "amazing spiderman"),
                         ["The Amazing Spider-Man", "Amazing Spider-Man"])

    def test_language_and_year_narrow_the_search(self):
        """A language keeps the series in it, and a year in the query keeps the series running that year."""
        self.assertEqual(self.names("series", "spiderman", ["it"]), ["Spiderman"])
        self.assertEqual(self.names("series", "spider 1990"), ["Spiderman"])
        self.assertEqual(self.names("series", "spider 2020"), ["Amazing Spider-Man"])

    def test_issues_are_found_by_series_and_number(self):
        """An issue is found by series name and "#12" or a final "12"; a series name alone finds no issue."""
        found, more = search_records("issue", "amazing spiderman #12")
        self.assertEqual([issue.series_id for issue in found], [self.amazing.pk])
        self.assertEqual(search_records("issue", "amazing spiderman 12")[0], found)
        self.assertEqual(search_records("issue", "amazing spiderman"), ([], False))

    def test_deleted_records_are_not_found(self):
        """A deleted publisher is left out of the results."""
        self.publisher.deleted = True
        self.publisher.save()
        self.assertEqual(self.names("publisher", "marvelous"), ["The Marvelous Group"])

    def test_search_view_returns_links_and_details(self):
        """The view lists records in the chosen language with full URL and years; unknown types find none."""
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:record-search"), {"type": "series", "q": "spiderman", "lang": "it"})
        self.assertContains(response, f'data-record-url="http://testserver/series/{self.spanish.pk}/"')
        self.assertContains(response, "1983–1993")
        self.assertNotContains(response, f"/series/{self.amazing.pk}/")
        response = self.client.get(reverse("forum:record-search"), {"type": "cover", "q": "Marvelous"})
        self.assertNotContains(response, "data-record-url")

    def cover(self, issue):
        """Add a cover to the issue."""
        from apps.gcd.models import Cover

        Cover.objects.create(issue=issue)

    def search(self, kind, query):
        """Get the record search for a type and a query, signed in as other."""
        self.client.force_login(self.other)
        return self.client.get(reverse("forum:record-search"), {"type": kind, "q": query})

    @override_settings(FAKE_IMAGES=True)
    def test_results_show_the_cover_of_issues_and_series(self):
        """Results show the cover of issues and series, an icon for publishers, and no "nocover" image."""
        from apps.gcd.models import Issue, Series

        Series.objects.filter(pk=self.amazing.pk).update(is_comics_publication=True)
        issue = Issue.objects.get(series=self.amazing)
        Series.objects.filter(pk=self.amazing.pk).update(first_issue=issue)
        self.cover(issue)
        self.assertContains(self.search("issue", "amazing spiderman #12"), "img/placeholder_small.jpg")
        self.assertContains(self.search("series", "amazing spiderman"), "img/placeholder_small.jpg", count=1)
        response = self.search("publisher", "marvelous")
        self.assertNotContains(response, "<img")
        self.assertContains(response, "<rect", count=2)
        self.assertNotContains(self.search("series", "spiderman"), "nocover")

    @override_settings(FAKE_IMAGES=True)
    def test_covers_cost_at_most_one_query_per_result(self):
        """Listing three series with covers takes at most two queries more than listing one of them."""
        from apps.gcd.models import Issue, Series

        for series in (self.amazing, self.spanish, self.later):
            Series.objects.filter(pk=series.pk).update(is_comics_publication=True)
            issue = Issue.objects.filter(series=series).first() or Issue.objects.create(
                series=series, number="1", sort_code=1)
            Series.objects.filter(pk=series.pk).update(first_issue=issue)
            self.cover(issue)
        self.search("series", "amazing spider-man 2018")
        with CaptureQueriesContext(connection) as one:
            self.search("series", "amazing spider-man 2018")
        with CaptureQueriesContext(connection) as three:
            self.search("series", "spider")
        self.assertContains(self.search("series", "spider"), "img/placeholder_small.jpg", count=3)
        self.assertLessEqual(len(three) - len(one), 2)

    def test_far_offsets_and_odd_numbers_are_refused(self):
        """A far offset queries no records; a non-ASCII or ten-digit offset gives the first page."""
        self.client.force_login(self.other)
        url = reverse("forum:record-search")
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url, {"type": "publisher", "q": "marvelous", "offset": "999999"})
        self.assertNotContains(response, "data-record-url")
        self.assertFalse([query for query in queries if "gcd_publisher" in query["sql"]])
        # Not a short number: the first page, at the cost of any first page.
        for odd in ("²", "1000000000"):
            response = self.client.get(url, {"type": "publisher", "q": "marvelous", "offset": odd})
            self.assertContains(response, "data-record-url", count=2)

    def test_more_results_focus_their_first_record_and_say_how_many(self):
        """Page one puts its count and "more below" in the status; the next page focuses its first record."""
        from apps.forum.records import SEARCH_LIMIT

        for number in range(SEARCH_LIMIT + 2):
            self.make_publisher(f"Marvelous {number}")
        self.client.force_login(self.other)
        url = reverse("forum:record-search")
        first = self.client.get(url, {"type": "publisher", "q": "marvelous", "prefix": "insert-id_content"})
        self.assertNotContains(first, "autofocus")
        self.assertContains(first, f'id="insert-id_content-status" hx-swap-oob="innerHTML">{SEARCH_LIMIT} '
                                   'records found, more below.')
        more = self.client.get(url, {"type": "publisher", "q": "marvelous", "offset": SEARCH_LIMIT})
        self.assertContains(more, "autofocus", count=1)
        self.assertNotContains(more, "hx-swap-oob")

    def test_more_results_come_in_pages(self):
        """The page at offset SEARCH_LIMIT holds the remaining records, none repeated from the first page."""
        from apps.forum.records import SEARCH_LIMIT

        for number in range(SEARCH_LIMIT + 2):
            self.make_publisher(f"Marvelous {number}")
        first, more = search_records("publisher", "marvelous")
        second, _ = search_records("publisher", "marvelous", offset=SEARCH_LIMIT)
        self.assertTrue(more)
        self.assertEqual(len(first) + len(second), SEARCH_LIMIT + 4)
        self.assertFalse({record.pk for record in first} & {record.pk for record in second})


class RecordsInTextTests(ForumTestCase):
    """Links to GCD record pages in a message, which link the topic to the records."""

    def setUp(self):
        """Create a publisher to link to."""
        super().setUp()
        self.publisher = self.make_publisher()

    def test_links_to_gcd_pages_in_a_reply_link_the_record(self):
        """A comics.org record link in a reply, even before a full stop, links the topic to the record."""
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {
            "content": f"See https://www.comics.org/publisher/{self.publisher.pk}/. "
                       "And https://example.com/publisher/1/"})
        self.assertEqual(list(DiscussionRecord.objects.values_list("object_id", flat=True)), [self.publisher.pk])

    def test_other_sites_are_ignored(self):
        """The path of a record page on another site is not a GCD record link."""
        self.assertEqual(records_in_text(f"https://example.com/publisher/{self.publisher.pk}/"), [])
