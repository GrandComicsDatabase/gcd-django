from email.message import EmailMessage as RawEmail
from unittest import mock

from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from apps.forum import mail as gateway
from apps.forum.models import (
    Category, Discussion, GroupEmailSubscription, IncomingEmail, OutgoingEmail, Post, TopicSubscription,
)

from .base import ForumTestCase


def raw_email(sender, to, subject, body, **headers):
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
    def setUp(self):
        super().setUp()
        self.author.email = "author@example.com"
        self.author.save()
        self.other.email = "other@example.com"
        self.other.save()


class OutgoingTests(MailTestCase):
    def test_reply_is_queued_for_followers_and_email_members_only(self):
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        reader = self.make_user("reader", "reader@example.com")
        GroupEmailSubscription.objects.create(user=reader, category=self.main)
        self.client.force_login(self.other)
        self.client.post(reverse("forum:reply", args=[self.discussion.slug]), {"content": "Hello list"})
        queued = set(OutgoingEmail.objects.values_list("user__username", flat=True))
        self.assertEqual(queued, {"author", "reader"})

    def test_members_only_group_is_not_mailed_to_outsiders(self):
        editor = Category.objects.get(slug="gcd-editor")
        editor.members.add(self.author)
        topic = self.make_topic("Editors", editor, self.author)
        GroupEmailSubscription.objects.create(user=self.other, category=editor)
        gateway.queue_post(topic.posts.get())
        self.assertFalse(OutgoingEmail.objects.filter(user=self.other).exists())

    def test_sent_email_threads_and_offers_one_click_unsubscribe(self):
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
        GroupEmailSubscription.objects.create(user=self.author, category=self.main)
        url = gateway.unsubscribe_url(self.author, "group", self.main.pk).replace("https://www.comics.org", "")
        client = Client(enforce_csrf_checks=True)
        self.assertContains(client.get(url), "You get an email for every post of gcd-main.")
        self.assertContains(client.post(url, {"List-Unsubscribe": "One-Click"}), "You are unsubscribed")
        self.assertFalse(GroupEmailSubscription.objects.exists())
        self.assertEqual(client.post(url[:-3] + "xx/").status_code, 404)

    def test_group_email_toggle(self):
        self.client.force_login(self.other)
        self.client.post(reverse("forum:group-email", args=[self.main.slug]))
        self.assertTrue(GroupEmailSubscription.objects.filter(user=self.other, category=self.main).exists())
        self.client.post(reverse("forum:group-email", args=[self.main.slug]))
        self.assertFalse(GroupEmailSubscription.objects.exists())

    def make_user(self, username, email):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username, email=email, password="x")


class IncomingTests(MailTestCase):
    def reply_to(self, user=None):
        return gateway.reply_address(user or self.other, self.discussion)

    def test_email_reply_becomes_a_threaded_post_without_quote_and_signature(self):
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
        record = gateway.process_message(raw_email(
            "author@example.com", self.reply_to(), "Re: topic", "Forged"))
        self.assertEqual((record.status, record.reason),
                         (IncomingEmail.Status.REJECTED, "sender does not own the reply address"))
        tampered = self.reply_to().replace("forum+r-", "forum+r-").rsplit("-", 1)[0] + "-0000@comics.org"
        record = gateway.process_message(raw_email("other@example.com", tampered, "Re: topic", "Tampered"))
        self.assertEqual(record.reason, "invalid reply signature")
        self.assertEqual(self.discussion.posts.count(), 1)

    def test_reply_to_a_closed_topic_is_rejected(self):
        self.discussion.is_locked = True
        self.discussion.save()
        record = gateway.process_message(raw_email("other@example.com", self.reply_to(), "Re: topic", "Late"))
        self.assertEqual(record.status, IncomingEmail.Status.REJECTED)

    def test_new_topic_by_email_needs_an_authenticated_known_sender(self):
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
        record = gateway.process_message(raw_email(
            "stranger@example.net", gateway.group_address(self.main), "Hello", "Can I post?",
            Authentication_Results="mx.comics.org; dmarc=pass header.from=example.net"))
        self.assertEqual(record.reason, "no single GCD account with this email")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["stranger@example.net"])
        self.assertEqual(mail.outbox[0].extra_headers["Auto-Submitted"], "auto-replied")

    def test_forged_unknown_sender_gets_no_reply(self):
        gateway.process_message(raw_email(
            "stranger@example.net", gateway.group_address(self.main), "Hello", "Spam"))
        self.assertEqual(len(mail.outbox), 0)

    def test_automatic_messages_and_repeats_are_not_posted(self):
        record = gateway.process_message(raw_email(
            "other@example.com", self.reply_to(), "Out of office", "Away", Auto_Submitted="auto-replied"))
        self.assertEqual(record.status, IncomingEmail.Status.IGNORED)
        raw = raw_email("other@example.com", self.reply_to(), "Re: topic", "Once", message_id="<once@x>")
        gateway.process_message(raw)
        gateway.process_message(raw)
        self.assertEqual(self.discussion.posts.filter(content="Once").count(), 1)

    @override_settings(FORUM_MAX_POSTS_PER_DAY=1)
    def test_flood_by_email_is_rejected(self):
        first = gateway.process_message(raw_email("other@example.com", self.reply_to(), "Re: topic", "One"))
        second = gateway.process_message(raw_email("other@example.com", self.reply_to(), "Re: topic", "Two"))
        self.assertEqual(first.status, IncomingEmail.Status.ACCEPTED)
        self.assertEqual((second.status, second.reason),
                         (IncomingEmail.Status.REJECTED, "You can post at most 1 messages in 24 hours."))

    def test_mailbox_is_read_and_marked_seen(self):
        raw = raw_email("other@example.com", self.reply_to(), "Re: topic", "From IMAP", message_id="<imap@x>")
        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.search.return_value = ("OK", [b"1"])
        client.fetch.return_value = ("OK", [(b"1 (RFC822 {10}", raw), b")"])
        config = {"host": "imap.example.com", "user": "forum", "password": "secret"}
        with override_settings(FORUM_EMAIL_IMAP=config), \
                mock.patch("imaplib.IMAP4_SSL", return_value=client):
            records = gateway.fetch_mailbox()
        self.assertEqual([record.status for record in records], [IncomingEmail.Status.ACCEPTED])
        client.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")


class TrimReplyTests(ForumTestCase):
    def test_quotes_in_several_languages_and_wrapped_headers_are_cut(self):
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
        text = "> question one\nanswer one\n> question two\nanswer two"
        self.assertEqual(gateway.trim_reply(text), text)
