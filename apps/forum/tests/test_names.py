import json
import re

from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.forum import mail as gateway
from apps.forum.models import Category, Notification, TopicSubscription
from apps.forum.utils import display_name

from .base import ForumTestCase


class NameTests(ForumTestCase):
    """People are named by their indexer's first and last name, never by the username GCD builds from the
    email address; there are no @mentions."""

    def setUp(self):
        """Create Maria Rossi, whose username comes from her email address as GCD registration builds it,
        with an indexer profile; she starts a topic in gcd-main, opened to the public, and replies to it."""
        from apps.indexer.models import Indexer

        super().setUp()
        country = self.make_publisher().country
        self.maria = get_user_model().objects.create_user(
            "maria.rossi1965_5123", password="x", first_name="Maria", last_name="Rossi")
        Indexer.objects.create(user=self.maria, country=country)
        Category.objects.filter(pk=self.main.pk).update(read_access=Category.Access.PUBLIC)
        TopicSubscription.objects.create(user=self.other, discussion=self.discussion)
        self.topic = self.make_topic("Who inked it?", self.main, self.maria)
        self.client.force_login(self.maria)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "I think Esposito."})
        self.reply = self.discussion.posts.latest("pk")

    def assertNamed(self, response):
        """The response names Maria Rossi and never shows her username."""
        self.assertContains(response, "Maria Rossi")
        self.assertNotContains(response, "maria.rossi1965")

    def test_pages_name_people_by_their_indexer_name(self):
        """Topic lists, topic pages (with the Reply and Quote buttons), post history, notifications and
        both feeds name the person, not the username."""
        self.client.force_login(self.other)
        self.assertNamed(self.client.get(self.main.get_absolute_url()))
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertNamed(page)
        self.assertContains(page, f"setReplyTarget({self.reply.pk}, {self.reply.pk}, 'Maria Rossi')")
        self.assertNamed(self.client.get(reverse("forum:notifications")))
        self.client.force_login(self.maria)
        self.assertNamed(self.client.get(reverse("forum:post-history", args=[self.reply.pk])))
        self.client.force_login(self.other)
        self.assertNamed(self.client.get(reverse("forum:feed")))
        self.assertNamed(self.client.get(reverse("forum:group-feed", args=["gcd-main"])))

    def test_structured_data_names_the_author(self):
        """The schema.org data of a public topic gives the author's name."""
        page = self.client.get(self.topic.get_absolute_url()).content.decode()
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(data["author"]["name"], "Maria Rossi")

    def test_emails_name_the_author(self):
        """An email of a post comes from "Maria Rossi via GCD Forum" and says "Maria Rossi wrote:"."""
        self.other.email = "other@example.com"
        message = gateway.build_message(self.reply, self.other)
        self.assertTrue(message.from_email.startswith("Maria Rossi via GCD Forum <"))
        self.assertTrue(message.body.startswith("Maria Rossi wrote:"))

    def test_accounts_without_a_name_show_as_gcd_user(self):
        """An account with no indexer profile, or a profile without a name, shows as "GCD user <id>"."""
        self.assertEqual(display_name(self.author), f"GCD user {self.author.pk}")
        get_user_model().objects.filter(pk=self.maria.pk).update(first_name="", last_name="")
        nameless = get_user_model().objects.get(pk=self.maria.pk)
        self.assertEqual(display_name(nameless), f"GCD user {nameless.pk}")

    def test_an_at_sign_notifies_nobody(self):
        """"@" before a username is plain text: the users it names, who do not follow the topic, get no
        notification."""
        self.client.force_login(self.author)
        self.client.post(reverse("forum:reply", args=[self.topic.slug]),
                         {"content": f"Ask @{self.other.username} and @{self.maria.username}"})
        self.assertTrue(self.topic.posts.filter(author=self.author).exists())
        self.assertFalse(Notification.objects.filter(post__discussion=self.topic).exists())
