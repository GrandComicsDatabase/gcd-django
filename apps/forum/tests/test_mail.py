from email.message import EmailMessage as RawEmail
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import Client, override_settings
from django.urls import reverse

from apps.forum import mail as gateway
from apps.forum.models import (
    Category, Discussion, GroupEmailSubscription, IncomingEmail, OutgoingEmail, Post, TopicSubscription,
)

from .base import ForumTestCase


def raw_email(sender, to, subject, body, **headers):
    """Raw email bytes; "_" in header keywords is "-"; the default Message-ID hashes sender, subject, body."""
    message = RawEmail()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = headers.pop("message_id", f"<{abs(hash((sender, subject, body)))}@example.com>")
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    message.set_content(body)
    return message.as_bytes()


@override_settings(FORUM_EMAIL_ADDRESS="forum@comics.org", SITE_URL="https://www.comics.org/")
class MailTestCase(ForumTestCase):
    """Base of the email tests: the comics.org forum address and site, and email addresses for the users."""

    def setUp(self):
        """Give author and other email addresses."""
        super().setUp()
        self.author.email = "author@example.com"
        self.author.save()
        self.other.email = "other@example.com"
        self.other.save()


class OutgoingTests(MailTestCase):
    """Emails of new posts: who gets them, their threading headers, retries and one-click unsubscribe."""

    def test_reply_is_queued_for_followers_and_email_members_only(self):
        """A reply is queued for the topic's followers and the group's email members, not for its author."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        reader = self.make_user("reader", "reader@example.com")
        GroupEmailSubscription.objects.create(user=reader, category=self.main)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hello list"})
        queued = set(OutgoingEmail.objects.values_list("user__username", flat=True))
        self.assertEqual(queued, {"author", "reader"})

    def test_members_only_group_is_not_mailed_to_outsiders(self):
        """An email member of a members-only group they cannot read gets no email of its posts."""
        editor = Category.objects.get(slug="gcd-editor")
        editor.members.add(self.author)
        topic = self.make_topic("Editors", editor, self.author)
        GroupEmailSubscription.objects.create(user=self.other, category=editor)
        gateway.queue_post(topic.posts.get())
        self.assertFalse(OutgoingEmail.objects.filter(user=self.other).exists())

    def test_sent_email_threads_and_offers_one_click_unsubscribe(self):
        """A reply's email threads under the first post, offers one-click unsubscribe and is sent once."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Threaded"})
        self.assertEqual(gateway.send_pending(), 1)
        message = mail.outbox[0]
        reply = self.discussion.posts.order_by("-pk").first()
        self.assertEqual(message.to, ["author@example.com"])
        self.assertEqual(message.subject, "[gcd-main] Re: A forum topic")
        self.assertEqual(message.extra_headers["Message-ID"], f"<forum-post-{reply.pk}@comics.org>")
        self.assertEqual(message.extra_headers["In-Reply-To"], f"<forum-post-{self.post.pk}@comics.org>")
        self.assertEqual(message.extra_headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertTrue(message.reply_to[0].startswith(f"forum+r-{self.author.pk}-{self.discussion.pk}-"))
        self.assertIn("Threaded", message.body)
        self.assertIsNotNone(OutgoingEmail.objects.get().sent_at)
        self.assertEqual(gateway.send_pending(), 0)

    def test_failed_send_is_retried_later(self):
        """A failed send records the attempt and the error, and the next run sends the email."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        gateway.queue_post(Post.objects.create(
            discussion=self.discussion, author=self.other, content="Retry", created_by=self.other,
            updated_by=self.other, ip_address="127.0.0.1"))
        with mock.patch("django.core.mail.EmailMessage.send", side_effect=OSError("SMTP down")):
            self.assertEqual(gateway.send_pending(), 0)
        item = OutgoingEmail.objects.get()
        self.assertEqual((item.attempts, item.sent_at), (1, None))
        self.assertIn("SMTP down", item.error)
        self.assertEqual(gateway.send_pending(), 1)

    def test_one_click_unsubscribe_needs_no_session_but_a_valid_signature(self):
        """The signed unsubscribe link works with no session or CSRF token; a changed signature gives 404."""
        GroupEmailSubscription.objects.create(user=self.author, category=self.main)
        url = gateway.unsubscribe_url(self.author, "group", self.main.pk).replace("https://www.comics.org", "")
        client = Client(enforce_csrf_checks=True)
        self.assertContains(client.get(url), "You get an email for every post of gcd-main.")
        self.assertContains(client.post(url, {"List-Unsubscribe": "One-Click"}), "You are unsubscribed")
        self.assertFalse(GroupEmailSubscription.objects.exists())
        self.assertEqual(client.post(url[:-3] + "xx/").status_code, 404)

    def make_user(self, username, email):
        """Create a user with this email address."""
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username, email=email, password="x")


class IncomingTests(MailTestCase):
    """Emails to the forum: replies and new topics, what is rejected or ignored, and the IMAP mailbox."""

    def reply_to(self, user=None):
        """The reply address of the topic for the user, other by default."""
        return gateway.reply_address(user or self.other, self.discussion)

    def test_email_reply_becomes_a_threaded_post_without_quote_and_signature(self):
        """An email reply becomes a post under its parent with no quote or signature, queued for followers."""
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        body = ("Yes, it is 1954.\n\n-- \nOther\n\n"
                "On Mon, 1 Jan 2026 at 10:00, Author via GCD Forum <forum@comics.org> wrote:\n> First post\n")
        record = gateway.process_message(raw_email(
            "Other <other@example.com>", self.reply_to(), "Re: [gcd-main] A forum topic", body,
            In_Reply_To=f"<forum-post-{self.post.pk}@comics.org>"))
        self.assertEqual(record.status, IncomingEmail.Status.ACCEPTED)
        self.assertEqual(record.post.content, "Yes, it is 1954.")
        self.assertEqual(record.post.parent, self.post)
        self.assertEqual(record.post.author, self.other)
        self.assertTrue(OutgoingEmail.objects.filter(user=self.author, post=record.post).exists())

    def test_reply_address_only_works_for_its_owner(self):
        """A reply address rejects other senders and a changed signature, and no post is created."""
        record = gateway.process_message(raw_email(
            "author@example.com", self.reply_to(), "Re: topic", "Forged"))
        self.assertEqual((record.status, record.reason),
                         (IncomingEmail.Status.REJECTED, "sender does not own the reply address"))
        tampered = self.reply_to().rsplit("-", 1)[0] + "-0000@comics.org"
        record = gateway.process_message(raw_email("other@example.com", tampered, "Re: topic", "Tampered"))
        self.assertEqual(record.reason, "invalid reply signature")
        self.assertEqual(self.discussion.posts.count(), 1)

    def test_reply_to_a_closed_topic_is_rejected(self):
        """An email reply to a locked topic is rejected."""
        self.discussion.is_locked = True
        self.discussion.save()
        record = gateway.process_message(raw_email("other@example.com", self.reply_to(), "Re: topic", "Late"))
        self.assertEqual(record.status, IncomingEmail.Status.REJECTED)

    def test_new_topic_by_email_needs_an_authenticated_known_sender(self):
        """An email to a group needs dmarc=pass to open a topic, by the sender's account, who follows it."""
        to = gateway.group_address(self.main)
        record = gateway.process_message(raw_email("other@example.com", to, "Missing credits", "Who drew it?"))
        self.assertEqual(record.reason, "sender not authenticated (no dmarc=pass)")
        record = gateway.process_message(raw_email(
            "other@example.com", to, "Missing credits", "Who drew it?", message_id="<new@example.com>",
            Authentication_Results="mx.comics.org; spf=pass; dkim=pass; dmarc=pass header.from=example.com"))
        self.assertEqual(record.status, IncomingEmail.Status.ACCEPTED)
        topic = Discussion.objects.get(title="Missing credits")
        self.assertEqual((topic.category, topic.author), (self.main, self.other))
        self.assertTrue(TopicSubscription.objects.filter(user=self.other, discussion=topic).exists())

    def test_unknown_authenticated_sender_gets_one_rejection_notice(self):
        """An authenticated sender without a GCD account gets one rejection notice, marked auto-replied."""
        record = gateway.process_message(raw_email(
            "stranger@example.net", gateway.group_address(self.main), "Hello", "Can I post?",
            Authentication_Results="mx.comics.org; dmarc=pass header.from=example.net"))
        self.assertEqual(record.reason, "no single GCD account with this email")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["stranger@example.net"])
        self.assertEqual(mail.outbox[0].extra_headers["Auto-Submitted"], "auto-replied")

    def test_forged_unknown_sender_gets_no_reply(self):
        """A sender without dmarc=pass gets no rejection notice, so forged senders get no backscatter."""
        gateway.process_message(raw_email(
            "stranger@example.net", gateway.group_address(self.main), "Hello", "Spam"))
        self.assertEqual(len(mail.outbox), 0)

    def test_automatic_messages_and_repeats_are_not_posted(self):
        """An auto-reply is ignored, and a message processed twice is posted once."""
        record = gateway.process_message(raw_email(
            "other@example.com", self.reply_to(), "Out of office", "Away", Auto_Submitted="auto-replied"))
        self.assertEqual(record.status, IncomingEmail.Status.IGNORED)
        raw = raw_email("other@example.com", self.reply_to(), "Re: topic", "Once", message_id="<once@x>")
        gateway.process_message(raw)
        gateway.process_message(raw)
        self.assertEqual(self.discussion.posts.filter(content="Once").count(), 1)

    @override_settings(FORUM_NEW_MAX_POSTS_PER_DAY=1)
    def test_flood_by_email_is_rejected(self):
        """An email reply over the daily post limit is rejected, with the limit as the reason."""
        first = gateway.process_message(raw_email("other@example.com", self.reply_to(), "Re: topic", "One"))
        second = gateway.process_message(raw_email("other@example.com", self.reply_to(), "Re: topic", "Two"))
        self.assertEqual(first.status, IncomingEmail.Status.ACCEPTED)
        self.assertEqual(second.status, IncomingEmail.Status.REJECTED)
        self.assertTrue(second.reason.startswith("You can post at most 1 messages in 24 hours"))

    def test_mailbox_is_read_and_marked_seen(self):
        """Unseen messages of the IMAP mailbox are posted, then flagged as seen."""
        raw = raw_email("other@example.com", self.reply_to(), "Re: topic", "From IMAP", message_id="<imap@x>")
        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.select.return_value = ("OK", [b"1"])
        client.search.return_value = ("OK", [b"1"])
        client.fetch.return_value = ("OK", [(b"1 (RFC822 {10}", raw), b")"])
        config = {"host": "imap.example.com", "user": "forum", "password": "secret"}
        with override_settings(FORUM_EMAIL_IMAP=config), \
                mock.patch("imaplib.IMAP4_SSL", return_value=client):
            records = gateway.fetch_mailbox()
        self.assertEqual([record.status for record in records], [IncomingEmail.Status.ACCEPTED])
        client.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")


class DeliveryGuardTests(MailTestCase):
    """What stops forum email from leaking or stalling: withdrawn posts, the right unsubscribe, the cron
    job's separate steps and lock, IMAP checks and logged rejection notices."""

    def queue_reply(self, content="A reply"):
        """A reply by other to the test topic, queued for author, who follows the topic."""
        TopicSubscription.objects.get_or_create(user=self.author, discussion=self.discussion)
        post = Post.objects.create(discussion=self.discussion, author=self.other, content=content,
                                   created_by=self.other, updated_by=self.other, ip_address="127.0.0.1")
        gateway.queue_post(post)
        return post

    def test_removed_posts_are_withdrawn_not_sent(self):
        """A post removed after it was queued is not emailed; its queue entry is closed as withdrawn."""
        post = self.queue_reply("My phone number is ...")
        post.delete()
        self.assertEqual(gateway.send_pending(), 0)
        self.assertEqual(mail.outbox, [])
        item = OutgoingEmail.objects.get()
        self.assertEqual((item.sent_at, item.attempts, item.error), (None, gateway.MAX_ATTEMPTS, gateway.WITHDRAWN))

    def test_topics_moved_out_of_reach_are_withdrawn(self):
        """A topic moved to a members-only group after a post was queued is not emailed to non-members."""
        self.queue_reply()
        Discussion.all_objects.filter(pk=self.discussion.pk).update(
            category=Category.objects.get(slug="gcd-editor"))
        self.assertEqual(gateway.send_pending(), 0)
        self.assertEqual(mail.outbox, [])

    def test_record_followers_unsubscribe_from_the_record(self):
        """The email of a new topic about a followed record links to stopping that follow, which works."""
        from apps.forum.models import RecordSubscription
        from apps.forum.records import record_content_type

        publisher = self.make_publisher()
        follow = RecordSubscription.objects.create(
            user=self.author, content_type=record_content_type("publisher"), object_id=publisher.pk)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:discussion-create"), {
            "category": self.main.pk, "title": "About the publisher",
            "content": f"See https://www.comics.org/publisher/{publisher.pk}/"})
        gateway.send_pending()
        url = gateway.unsubscribe_url(self.author, "record", follow.pk)
        self.assertIn(f"Stop following the record: {url}", mail.outbox[0].body)
        path = url.replace("https://www.comics.org", "")
        self.assertContains(Client().get(path), f"You get an email for new topics about {publisher}.")
        Client().post(path)
        self.assertFalse(RecordSubscription.objects.exists())

    def test_a_mailbox_failure_does_not_stop_the_sending(self):
        """When the mailbox cannot be read, forum_mail still sends the queue, logs the failure and exits with
        an error naming the step."""
        import imaplib

        self.queue_reply()
        with (mock.patch("apps.forum.management.commands.forum_mail.fetch_mailbox",
                         side_effect=imaplib.IMAP4.error("LOGIN failed")),
              self.assertLogs("apps.forum.management.commands.forum_mail", "ERROR"),
              self.assertRaisesMessage(CommandError, "could not read the mailbox")):
            call_command("forum_mail", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_a_run_stops_while_another_one_works(self):
        """While another connection holds the run's lock, forum_mail sends nothing and says why."""
        from django.db import connection

        from apps.forum.management.commands.forum_mail import lock_name

        self.queue_reply()
        other = connection.copy()
        try:
            with other.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0)", [lock_name()])
            out = StringIO()
            call_command("forum_mail", "--no-fetch", stdout=out)
        finally:
            other.close()
        self.assertIn("Another forum_mail run is still working", out.getvalue())
        self.assertEqual(mail.outbox, [])
        call_command("forum_mail", "--no-fetch", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_imap_refusals_and_timeouts(self):
        """The mailbox is opened with a timeout, and a refused folder raises an IMAP error."""
        import imaplib

        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.select.return_value = ("NO", [b"no such folder"])
        config = {"host": "imap.example.com", "user": "forum", "password": "secret", "folder": "Forum"}
        with (override_settings(FORUM_EMAIL_IMAP=config),
              mock.patch("imaplib.IMAP4_SSL", return_value=client) as server):
            with self.assertRaisesMessage(imaplib.IMAP4.error, "cannot open the folder Forum"):
                gateway.fetch_mailbox()
        server.assert_called_once_with("imap.example.com", 993, timeout=gateway.TIMEOUT)
        client.search.assert_not_called()

    def test_a_rejection_notice_that_cannot_be_sent_is_logged(self):
        """When the notice of a rejected email cannot be sent, the failure is logged."""
        record = IncomingEmail(message_id="<x@example.com>", subject="Hello", reason="no single GCD account")
        with (mock.patch("django.core.mail.EmailMessage.send", side_effect=OSError("SMTP down")),
              self.assertLogs("apps.forum.mail", "ERROR") as logs):
            gateway._send_rejection("stranger@example.com", record)
        self.assertIn("<x@example.com>", logs.output[0])


class TrimReplyTests(ForumTestCase):
    """How trim_reply keeps the new text of an email reply and cuts the quoted message."""

    def test_quotes_in_several_languages_and_wrapped_headers_are_cut(self):
        """Quote headers (English wrapped, Italian, German, "Original Message") and a final quote are cut."""
        cases = [
            "New text\n\nOn Tue, 2 Jan 2026 at 09:00, Someone via GCD Forum\n<forum@comics.org> wrote:\n> old",
            "New text\n\nIl giorno mar 2 gen 2026 alle ore 09:00 Someone ha scritto:\n> vecchio",
            "New text\n\nAm Di., 2. Jan. 2026 um 09:00 Uhr schrieb Someone:\n> alt",
            "New text\n-----Original Message-----\nFrom: Someone",
            "New text\n> trailing quote\n",
        ]
        for text in cases:
            self.assertEqual(gateway.trim_reply(text), "New text", text)

    def test_inline_quotes_inside_the_answer_are_kept(self):
        """Quotes answered line by line inside the message are kept unchanged."""
        text = "> question one\nanswer one\n> question two\nanswer two"
        self.assertEqual(gateway.trim_reply(text), text)


class LockTests(ForumTestCase):
    """The cron job's MySQL named lock, shared by the whole server, is named for the database."""

    def test_the_lock_name_carries_the_database(self):
        """Two sites on one MySQL server take different locks."""
        from django.db import connection

        from apps.forum.management.commands.forum_mail import lock_name

        self.assertIn(connection.settings_dict["NAME"][:40], lock_name())
        self.assertLessEqual(len(lock_name()), 64)
