from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from apps.forum.models import Category, ContentRevision, Discussion, Post, Report, TopicSubscription
from apps.forum.records import normalize
from apps.forum.views import ROOTS_PER_PAGE

from .base import ForumTestCase


class PageTests(ForumTestCase):
    """What pages show and where actions lead: history, edits, errors, sidebar counts and drafts."""

    def edit(self, user, post, content):
        """Edit the post as the user; return the response."""
        self.client.force_login(user)
        return self.client.post(reverse("forum:post-edit", args=[post.pk]), {"content": content})

    def test_earlier_versions_are_for_the_author_and_moderators(self):
        """Readers see that a post was edited but not its earlier versions; the author does, and a superuser
        can delete a version from the admin to redact it."""
        self.edit(self.author, self.post, "Without my address")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("forum:post-history", args=[self.post.pk])).status_code, 404)
        self.assertNotContains(self.client.get(self.discussion.get_absolute_url()),
                               reverse("forum:post-history", args=[self.post.pk]))
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse("forum:post-history", args=[self.post.pk])), "First post")
        admin = get_user_model().objects.create_superuser("forum-admin", "admin@example.com", "x")
        self.client.force_login(admin)
        revision = ContentRevision.objects.filter(
            content_type=ContentType.objects.get_for_model(Post), object_id=self.post.pk).last()
        self.client.post(reverse("admin:forum_contentrevision_delete", args=[revision.pk]), {"post": "yes"})
        self.assertFalse(ContentRevision.objects.filter(pk=revision.pk).exists())

    @override_settings(FORUM_NEW_MAX_EDITS_PER_DAY=1)
    def test_edits_are_limited_per_day(self):
        """Past the daily edit limit an edit is refused with the reason, and the text stays."""
        self.edit(self.author, self.post, "Edit one")
        response = self.edit(self.author, self.post, "Edit two")
        self.assertContains(response, "You can make at most 1 edits in 24 hours")
        self.assertEqual(Post.objects.get(pk=self.post.pk).content, "Edit one")

    def test_refused_actions_come_back_to_the_page_with_the_reason(self):
        """A report too long once its line breaks are counted as the browser does is sent; a report of a
        handled report, a move to a group one cannot post in and an objection after the consensus ended
        come back to the topic with a message, the text of the objection included."""
        # 1080 characters as sent, 900 as the browser counted them.
        reason = "Line\r\n" * 180
        self.client.force_login(self.other)
        self.client.post(reverse("forum:report", args=["post", self.post.pk]), {"reason": reason})
        report = Report.objects.get()
        self.assertEqual(report.reason, reason.replace("\r\n", "\n").strip())
        Report.objects.filter(pk=report.pk).update(status=Report.Status.DISMISSED)
        self.main.moderators.add(self.author)
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:report-resolve", args=[report.pk]), {"action": "dismiss"},
                                    follow=True)
        self.assertContains(response, "already handled by another moderator")
        response = self.client.post(reverse("forum:discussion-move", args=[self.discussion.slug]),
                                    {"category": 999999}, follow=True)
        self.assertContains(response, "Choose a group you can post in.")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:consensus-object", args=[self.discussion.slug]),
                                    {"reason": "Too strict."}, follow=True)
        self.assertContains(response, "The consensus step is over")
        self.assertContains(response, "Your text: Too strict.")

    def test_errors_of_panel_forms_land_where_the_message_is(self):
        """An error of a panel form goes back to the top of the topic, not to the panel's anchor."""
        self.client.force_login(self.author)
        response = self.client.post(reverse("forum:change-link", args=[self.discussion.slug]), {"changeset": "x"})
        self.assertEqual(response.url, self.discussion.get_absolute_url())

    def test_a_top_level_reply_from_an_earlier_page_opens_its_page(self):
        """A top-level reply sent from a page that is not the last opens the page that holds it."""
        for number in range(ROOTS_PER_PAGE):
            Post.objects.create(discussion=self.discussion, author=self.author, content=f"Post {number}",
                                created_by=self.author, updated_by=self.author, ip_address="127.0.0.1")
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "Late reply", "page": "1"}, HTTP_HX_REQUEST="true")
        post = Post.objects.get(content="Late reply")
        self.assertEqual(response["HX-Redirect"], post.get_absolute_url())
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "On the last page", "page": "2"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "On the last page")

    def test_the_sidebar_counts_the_topics_one_can_list(self):
        """A group one posts in but cannot read counts only one's own topics."""
        error = Category.objects.get(slug="gcd-error")
        self.make_topic("Somebody's report", error, self.author)
        self.make_topic("My report", error, self.other)
        self.client.force_login(self.other)
        response = self.client.get(reverse("forum:index"))
        counts = {group.slug: group.topic_count
                  for section in response.context["sections"] for group in section["groups"]}
        self.assertEqual(counts["gcd-error"], 1)

    def test_record_names_with_sharp_s_are_compared_as_written(self):
        """"ß" stays "ß" in the search's normal form, as the database compares names letter by letter."""
        self.assertEqual(normalize("Straße des Hasses"), "straßedeshasses")

    def test_follow_buttons_do_what_they_say(self):
        """The topic's Follow button sends the state it asks for, so a stale or repeated click does that; a
        reply sent with htmx also updates the button, since replying follows the topic."""
        url = reverse("forum:discussion-follow", args=[self.discussion.slug])
        self.client.force_login(self.other)
        for _ in range(2):
            self.client.post(url, {"follow": "1"}, HTTP_HX_REQUEST="true")
        self.assertTrue(TopicSubscription.objects.filter(user=self.other, discussion=self.discussion).exists())
        self.client.post(url, {"follow": "0"})
        self.assertFalse(TopicSubscription.objects.filter(user=self.other, discussion=self.discussion).exists())
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hi"},
                                    HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="follow-topic"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertContains(response, "Following ✓")

    def test_reply_works_without_scripts(self):
        """A Reply link opens the form aimed at the post; a reply with errors sent without htmx comes back
        in a page of the forum, with the text."""
        self.client.force_login(self.other)
        page = self.client.get(self.discussion.get_absolute_url(), {"reply_to": self.post.pk})
        self.assertEqual(page.context["reply_form"]["parent"].value(), self.post.pk)
        self.assertContains(page, f"Reply to GCD user {self.author.pk}")
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]),
                                    {"content": "x" * 40000})
        self.assertContains(response, "<html", status_code=422)
        self.assertContains(response, "at most 32000 characters", status_code=422)

    def test_group_email_choice_is_saved_with_its_button(self):
        """The group's email choice has a visible Save button and does not save on every change."""
        self.client.force_login(self.other)
        page = self.client.get(self.main.get_absolute_url())
        self.assertNotContains(page, "requestSubmit")
        self.assertContains(page, '<button class="btn-blue-editing inline-block m-0">Save</button>', html=True)

    def test_unread_notifications_say_so_in_words(self):
        """An unread notification says "Unread" to screen readers, not only in bold."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hi"})
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse("forum:notifications")), '<span class="sr-only">Unread: </span>')

    def test_a_published_topic_tells_the_next_page_once(self):
        """After a new topic is published, the next page carries the mark that drops its draft, once."""
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "A new topic", "content": "Text"}, follow=True)
        self.assertContains(response, 'data-draft-published="1"')
        self.assertContains(self.client.get(Discussion.objects.get(title="A new topic").get_absolute_url()),
                            'data-draft-published=""')

    def test_a_reply_sent_by_htmx_offers_its_edit_item(self):
        """The new post the reply answer inserts has Edit in its menu, as after a reload."""
        self.client.force_login(self.other)
        response = self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Mine"},
                                    HTTP_HX_REQUEST="true")
        post = Post.objects.get(content="Mine")
        self.assertContains(response, reverse("forum:post-edit", args=[post.pk]))

    def test_reply_links_open_the_page_of_their_post(self):
        """Without the script, Reply opens the page holding the post, with the reply box aimed at it."""
        self.client.force_login(self.other)
        page = self.client.get(self.discussion.get_absolute_url())
        self.assertContains(page, f'href="?post={self.post.pk}&amp;reply_to={self.post.pk}#reply-form-container"')

    def test_the_preview_shows_the_whole_of_a_long_message(self):
        """A message longer than 20,000 characters, within the post limit, previews to its end."""
        self.client.force_login(self.other)
        text = "word " * 5000 + "TheEnd"
        response = self.client.post(reverse("forum:markdown-preview"), {"content": text})
        self.assertContains(response, "TheEnd")

    def test_record_names_are_loaded_with_what_they_read(self):
        """Every relation named in NAME_RELATIONS exists, so each record type loads with one query."""
        from apps.forum.records import record_model
        from apps.forum.views import NAME_RELATIONS

        for key, relations in NAME_RELATIONS.items():
            str(record_model(key).objects.select_related(*relations).query)
