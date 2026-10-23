import time
from email.message import EmailMessage as RawEmail

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory
from django.urls import reverse

from apps.forum import mail as gateway
from apps.forum.forms import MAX_CONTENT
from apps.forum.models import IncomingEmail, Post
from apps.forum.records import MAX_LINKS, records_in_text
from apps.forum.search import Query, excerpt
from apps.forum.templatetags.forum_tags import MAX_CARDS, record_cards, safe_markdown
from apps.forum.utils import get_client_ip, to_id

from .base import ForumTestCase

# Rendering a few thousand "[" took minutes before the bounds; the bounded code takes well under a second.
SLOW = 5


class InputTests(ForumTestCase):
    """Typed ids, pasted links and signatures that used to end in a 500 get the view's own answer."""

    def test_only_ascii_digits_are_ids(self):
        """Ids are ASCII digits that fit the id columns; Unicode digits and over-long numbers are not."""
        self.assertEqual([to_id(value) for value in ("12", " 7 ", "²", "٣", "1" * 19, "", None, "-1")],
                         [12, 7, None, None, None, None, None, None])

    def test_unicode_digits_in_query_strings_are_ignored(self):
        """A topic page and its update check asked with "²" as a number answer as without it."""
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.discussion.get_absolute_url(), {"post": "²"}).status_code, 200)
        url = reverse("forum:discussion-updates", args=[self.discussion.slug])
        self.assertEqual(self.client.get(url, {"after": "²"}).status_code, self.client.get(url).status_code)

    def test_a_non_ascii_unsubscribe_signature_is_a_404(self):
        """An unsubscribe link whose signature is not ASCII is a wrong link (404), not an error."""
        url = reverse("forum:email-unsubscribe", args=[self.other.pk, "topic", self.discussion.pk, "é"])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_a_link_cut_by_full_width_punctuation_is_skipped(self):
        """A comics.org host followed by "？" is not a record link: posting and reading the topic work."""
        text = "请看 https://www.comics.org？谢谢"
        self.assertEqual(records_in_text(text), [])
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": text})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(self.discussion.get_absolute_url()), "谢谢")

    def test_unreadable_client_addresses_are_logged(self):
        """An address that is not an IP is stored as 0.0.0.0, with a warning in the log."""
        request = RequestFactory().get("/", REMOTE_ADDR="not an address")
        with self.assertLogs("apps.forum.utils", "WARNING"):
            self.assertEqual(get_client_ip(request), "0.0.0.0")


class LoadTests(ForumTestCase):
    """Bounds on the work one message costs: its length, its brackets and its GCD links."""

    def links(self, count):
        """Links to count publisher pages that do not exist."""
        return [f"https://www.comics.org/publisher/{900000000 + number}/" for number in range(count)]

    def test_messages_are_limited_in_length(self):
        """A reply over MAX_CONTENT characters is refused with 422; an email that long is rejected."""
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "x" * (MAX_CONTENT + 1)})
        self.assertContains(response, f"at most {MAX_CONTENT} characters", status_code=422)
        self.other.email = "other@example.com"
        self.other.save()
        message = RawEmail()
        message["From"] = "other@example.com"
        message["To"] = gateway.reply_address(self.other, self.discussion)
        message["Subject"] = "Re: A forum topic"
        message["Message-ID"] = "<long@example.com>"
        message.set_content("x" * (MAX_CONTENT + 1))
        record = gateway.process_message(message.as_bytes())
        self.assertEqual((record.status, record.reason),
                         (IncomingEmail.Status.REJECTED, f"message longer than {MAX_CONTENT:,} characters"))

    def test_many_brackets_render_quickly_as_text(self):
        """Past MAX_BRACKET_WORK characters read to match brackets, "[" are plain text, so a post of brackets
        renders at once; below it links work."""
        self.assertIn('<a href="https://example.com/"', safe_markdown("[a](https://example.com/)"))
        started = time.monotonic()
        html = safe_markdown("[a](https://example.com/) " + "[" * 20000)
        self.assertLess(time.monotonic() - started, SLOW)
        self.assertNotIn('<a href="https://example.com/"', html)
        self.assertIn("[a](", html)

    def test_search_excerpts_of_bracket_runs_are_quick(self):
        """The excerpt of a post made of brackets is built at once and still marks the searched word."""
        started = time.monotonic()
        piece = excerpt("[" * 20000 + " spider", Query("spider"))
        self.assertLess(time.monotonic() - started, SLOW)
        self.assertIn("<mark>spider</mark>", piece)

    def test_only_the_first_gcd_links_of_a_message_are_read(self):
        """A message's first MAX_LINKS GCD links are looked up, and no more."""
        publisher = self.make_publisher()
        real = f"https://www.comics.org/publisher/{publisher.pk}/"
        self.assertEqual(records_in_text(" ".join(self.links(MAX_LINKS - 1) + [real])), [("publisher", publisher)])
        self.assertEqual(records_in_text(" ".join(self.links(MAX_LINKS) + [real])), [])

    def test_a_post_shows_at_most_max_cards_records(self):
        """A post linking more records than MAX_CARDS shows MAX_CARDS cards, with one lookup per card."""
        links = [f"https://www.comics.org/publisher/{self.make_publisher(f'Publisher {n}').pk}/"
                 for n in range(MAX_CARDS + 2)]
        post = Post(content=" ".join(links))
        self.assertEqual(len(record_cards(post)["cards"]), MAX_CARDS)


class StorageTests(ForumTestCase):
    """The text people write is stored whole, emoji included, whatever the server's default charset."""

    def test_user_text_columns_are_utf8mb4(self):
        """The columns of user text (fields with db_collation, as upstream #746) are utf8mb4_unicode_ci in
        the database, and a reply with an emoji is kept."""
        from django.apps import apps

        from apps.forum.models import UTF8MB4

        fields = [(model._meta.db_table, field.column) for model in apps.get_app_config("forum").get_models()
                  for field in model._meta.local_fields if getattr(field, "db_collation", None)]
        self.assertGreaterEqual(len(fields), 15)
        with connection.cursor() as cursor:
            for table, column in fields:
                cursor.execute("SELECT COLLATION_NAME FROM information_schema.COLUMNS "
                               "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                               [table, column])
                self.assertEqual(cursor.fetchone()[0], UTF8MB4, f"{table}.{column}")
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hot 🔥 cover"})
        self.assertTrue(self.discussion.posts.filter(content="Hot 🔥 cover").exists())


class AdminTests(ForumTestCase):
    """Admin forms of production-size relations use raw ids, not a <select> of every row."""

    def test_topic_admin_uses_raw_ids_and_keeps_the_forum_marks(self):
        """The topic change form has raw id inputs for its topic and voting links, and shows the counters,
        the review flag and the marks set by forum actions read-only, so saving cannot write them back."""
        admin = get_user_model().objects.create_superuser("forum-admin", "admin@example.com", "x")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:forum_discussion_change", args=[self.discussion.pk]))
        for field in ("duplicate_of", "agenda_item", "ballot"):
            self.assertNotContains(response, f'<select name="{field}"')
            self.assertContains(response, f'name="{field}"')
        for field in ("answer", "fixed_by", "consensus_sought_by", "post_count", "views_count", "awaiting_review"):
            self.assertNotContains(response, f'name="{field}"')
        response = self.client.get(reverse("admin:forum_category_change", args=[self.main.pk]))
        self.assertNotContains(response, '<select name="members"')


class RenderCostTests(ForumTestCase):
    """Text that would make Markdown or the search excerpts read the same characters again and again."""

    def test_unclosed_brackets_before_a_long_text_render_quickly(self):
        """300 "[" before a long text are plain text, so the post renders at once; links elsewhere work."""
        started = time.monotonic()
        html = safe_markdown("[a](https://example.com/) " + "[" * 300 + "x" * 31000)
        self.assertLess(time.monotonic() - started, SLOW)
        self.assertNotIn('<a href="https://example.com/"', html)

    def test_long_posts_keep_their_links(self):
        """A long post with many links and a few stray brackets keeps every link."""
        text = "Notes [sic " + " ".join(f"[issue {n}](https://example.com/{n}/)" for n in range(150))
        self.assertEqual(safe_markdown(text + " words" * 4000).count("<a href"), 150)

    def test_excerpts_of_empty_line_runs_are_quick(self):
        """A post of thousands of empty lines is excerpted at once, with the word marked."""
        started = time.monotonic()
        piece = excerpt("spider" + "\n" * 30000, Query("spider"))
        self.assertLess(time.monotonic() - started, SLOW)
        self.assertIn("<mark>spider</mark>", piece)

    def test_cards_count_records_not_other_links(self):
        """Links to changes or searches do not use up the cards of a post: the record after them shows."""
        publisher = self.make_publisher()
        others = [f"https://www.comics.org/changeset/{number}/" for number in range(MAX_CARDS + 2)]
        post = Post(content=" ".join(others + [f"https://www.comics.org/publisher/{publisher.pk}/"]))
        self.assertEqual(len(record_cards(post)["cards"]), 1)
