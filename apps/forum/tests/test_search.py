from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.forum.models import Category, ContentRevision, Discussion, Post
from apps.forum.search import Query, excerpt

from .base import ForumTestCase


# InnoDB adds rows to a FULLTEXT index when they are committed, so these tests commit.
@override_settings(FORUM_REVIEW_FIRST_POSTS=False)
class SearchTests(TransactionTestCase):
    """Full-text search of the topic lists: prefixes, phrases, author and date filters, and access."""

    make_topic = ForumTestCase.make_topic

    def _fixture_teardown(self):
        """Delete all posts, topics, revisions and the users author and other; the groups stay."""
        # Remove what the test made instead of emptying every table, which would also remove
        # the groups of the data migration that the other tests use.
        Post.all_objects.all().hard_delete()
        Discussion.all_objects.all().hard_delete()
        ContentRevision.objects.all().delete()
        get_user_model().objects.filter(username__in=("author", "other")).delete()

    def setUp(self):
        """Create two gcd-main topics, with Spider-Man in a post and in a title, and sign in as other."""
        users = get_user_model().objects
        self.author = users.create_user("author", password="x")
        self.other = users.create_user("other", password="x", first_name="Anna", last_name="De Luca-Ferri")
        self.main = Category.objects.get_or_create(slug="gcd-main", defaults={"name": "gcd-main"})[0]
        self.editors = Category.objects.get_or_create(
            slug="gcd-editor", defaults={"name": "gcd-editor", "read_access": Category.Access.MEMBERS})[0]
        self.spider = self.make_topic("Missing credits", self.main, self.author,
                                      "Who inked The Amazing Spider-Man #129?")
        self.titled = self.make_topic("Spider-Man reprints in Italy", self.main, self.author, "A list.")
        self.client.force_login(self.other)

    def search(self, text, **params):
        """Search the forum home page for the text; return the titles found, in order, and the response."""
        response = self.client.get(reverse("forum:index"), {"q": text, **params})
        return [topic.title for topic in response.context["discussions"]], response

    def test_words_match_as_prefixes_and_titles_rank_first(self):
        """The word "spider" finds Spider-Man; the title match ranks first, and excerpts mark the word."""
        titles, response = self.search("spider")
        self.assertEqual(titles, ["Spider-Man reprints in Italy", "Missing credits"])
        self.assertContains(response, "The Amazing <mark>Spider</mark>-Man #129?")

    def test_every_word_and_phrases_are_required(self):
        """Every word is required, and a quoted phrase must appear with its words in that order."""
        self.assertEqual(self.search("amazing inked")[0], ["Missing credits"])
        self.assertEqual(self.search("amazing italy")[0], [])
        self.assertEqual(self.search('"amazing spider"')[0], ["Missing credits"])
        self.assertEqual(self.search('"spider amazing"')[0], [])

    def test_author_and_dates_filter_the_posts(self):
        """The by:, before: and after: filters search only the posts by those people or in that period.

        by: matches the start of any word of the first or last name; a name nobody who posted has finds
        nothing, and the username is not a name.
        """
        Post.objects.create(discussion=self.titled, author=self.other, content="Spider-Man in Topolino?",
                            created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
        for name in ("by:anna", 'by:"Anna De Luca"', "by:ferri", 'BY:"luca"'):
            self.assertEqual(self.search(f"spider {name}")[0], ["Spider-Man reprints in Italy"], name)
        self.assertEqual(self.search("spider by:other")[0], [])
        self.assertEqual(self.search('by:"Anna Rossi"')[0], [])
        old = timezone.now() - timedelta(days=400)
        Post.all_objects.filter(discussion=self.spider).update(created_at=old)
        cutoff = (timezone.now() - timedelta(days=30)).date().isoformat()
        self.assertEqual(self.search(f"spider before:{cutoff}")[0], ["Missing credits"])
        self.assertEqual(self.search(f"amazing after:{cutoff}")[0], [])

    def test_hidden_content_is_not_found(self):
        """Posts awaiting review, removed topics and groups the user cannot read stay out of the results."""
        secret = self.make_topic("Editors business", self.editors, self.author, "Secret spider plan")
        self.assertNotIn("Editors business", self.search("secret")[0])
        Post.objects.filter(discussion=self.spider).update(awaiting_review=True)
        Post.all_objects.filter(discussion=self.titled).update(is_deleted=True)
        Discussion.all_objects.filter(pk=self.titled.pk).update(is_deleted=True)
        self.assertEqual(self.search("spider")[0], [])
        self.client.force_login(self.author)
        self.editors.members.add(self.author)
        self.assertEqual(self.search("secret")[0], [secret.title])

    def test_short_words_search_titles(self):
        """A word too short for the index, such as "dc", is searched in the titles."""
        self.make_topic("DC in 1940", self.main, self.author, "Text")
        self.assertEqual(self.search("dc")[0], ["DC in 1940"])

    def test_hidden_topics_do_not_take_the_places_of_readable_ones(self):
        """The ranking keeps only the topics the user can list before it is cut, so a better match in a group
        the user cannot read does not push a readable one out of the results."""
        self.make_topic("Editors business", self.editors, self.author, "Spider spider spider spider plan")
        # One post kept from the ranking: before the access filter it would be the editors' post.
        with mock.patch("apps.forum.search.POSTS", 1):
            self.assertEqual(self.search("spider")[0], ["Spider-Man reprints in Italy", "Missing credits"])

    def test_filters_not_understood_are_named(self):
        """A date not written YYYY-MM-DD is not searched as words, and the page says it was ignored; a by:
        name nobody who posted has finds nothing, and the page says so."""
        titles, response = self.search("spider after:2020-1-5")
        self.assertEqual(titles, ["Spider-Man reprints in Italy", "Missing credits"])
        self.assertContains(response, "after:2020-1-5 was ignored: write dates as YYYY-MM-DD")
        titles, response = self.search("spider by:Nessuno")
        self.assertEqual(titles, [])
        self.assertContains(response, "Nobody named “Nessuno” posted in the topics searched.")

    def test_search_inside_a_group(self):
        """The search box of a group page searches that group's topics."""
        response = self.client.get(self.main.get_absolute_url(), {"q": "inked"})
        self.assertEqual([topic.title for topic in response.context["discussions"]], ["Missing credits"])


class QueryTests(ForumTestCase):
    """Parsing of a search text with Query, and the excerpts that mark the searched words."""

    def test_query_parts(self):
        """Query parses words, phrases, by: with a name and a valid after: date, then builds the boolean
        search; by: finds the author by first and last name, and a date it cannot read is set aside."""
        get_user_model().objects.filter(pk=self.author.pk).update(first_name="Ada", last_name="Lovelace")
        query = Query('the "Amazing Spider-Man" kirby by:"Ada Lovelace" after:2020-01-31 before:bad X')
        self.assertEqual((query.words, query.phrases, query.authors, query.after, query.ignored),
                         (["kirby"], [["amazing", "spider", "man"]], [self.author.pk],
                          timezone.datetime(2020, 1, 31).date(), ["before:bad"]))
        self.assertEqual(query.boolean(), '+kirby* +"amazing spider man"')

    def test_excerpt_escapes_and_marks(self):
        """An excerpt escapes HTML, drops Markdown marks and link addresses, and marks the searched word."""
        text = excerpt("A <b>bold</b> [link to Kirby](https://www.comics.org/creator/1/) by **Kirby**",
                       Query("kirby"))
        self.assertEqual(text, "A &lt;b&gt;bold&lt;/b&gt; link to <mark>Kirby</mark> by <mark>Kirby</mark>")


    def test_by_counts_only_posts_the_searcher_can_read(self):
        """A name whose only posts are in a group the searcher cannot read is not found by by:."""
        from apps.forum.models import Category
        from apps.forum.access import accessible_discussions

        writer = get_user_model().objects.create_user("writer", password="x", first_name="Ida", last_name="Hidden")
        editors = Category.objects.get(slug="gcd-editor")
        self.make_topic("Editors only", editors, writer)
        self.assertFalse(Query("by:ida", accessible_discussions(self.other)).authors)
        self.assertTrue(Query("by:ida").authors)
