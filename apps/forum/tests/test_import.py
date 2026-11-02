import mailbox
import os
import tempfile
from datetime import datetime, timezone
from io import StringIO

from django.core import mail
from django.core.management import call_command

from apps.forum.models import Discussion, IncomingEmail, Notification, OutgoingEmail, TopicSubscription

from .test_mail import raw_email
from .base import ForumTestCase


class MboxImportTests(ForumTestCase):
    """Import of an email list archive (mbox) into gcd-main with the forum_import_mbox command."""

    def setUp(self):
        """Give other an email address, have author follow the topic and create a temporary mbox file."""
        super().setUp()
        self.other.email = "other@example.com"
        self.other.save()
        TopicSubscription.objects.create(user=self.author, discussion=self.discussion)
        handle, self.path = tempfile.mkstemp(suffix=".mbox")
        os.close(handle)
        self.addCleanup(os.remove, self.path)

    def write(self, *messages):
        """Add the messages to the mbox file."""
        box = mailbox.mbox(self.path)
        for message in messages:
            box.add(message)
        box.flush()
        box.close()

    def run_import(self, *extra):
        """Run forum_import_mbox on the file for gcd-main, with author as archive user; return its output."""
        out = StringIO()
        call_command("forum_import_mbox", self.path, "--group", "gcd-main",
                     "--archive-user", self.author.username, *extra, stdout=out)
        return out.getvalue()

    def message(self, sender, subject, body, message_id, date, **headers):
        """A raw message to the gcd-main Google Group, with this Message-ID and Date."""
        return raw_email(sender, "gcd-main@googlegroups.com", subject, body, message_id=message_id,
                         Date=date, **headers)

    def archive(self):
        """Jane's question (she has no account), other's answer, first in the file, and Jane's thanks."""
        return (
            # Out of order on purpose: the reply comes first in the file.
            self.message("Other <other@example.com>", "Re: [gcd-main] Indicia dates", "They differ.\n\n"
                         "On Mon, 2 Jan 2006 at 10:00, Jane wrote:\n> Which date?", "<b@x>",
                         "Tue, 03 Jan 2006 09:00:00 +0000", In_Reply_To="<a@x>", References="<a@x>"),
            self.message("Jane Doe <jane@example.net>", "[gcd-main] Indicia dates", "Which date?",
                         "<a@x>", "Mon, 02 Jan 2006 10:00:00 +0000"),
            self.message("Jane Doe <jane@example.net>", "Re: [gcd-main] Indicia dates", "Thanks!",
                         "<c@x>", "Wed, 04 Jan 2006 08:00:00 +0000"),
        )

    def test_archive_becomes_threaded_topics_with_original_dates(self):
        """The archive becomes one threaded topic, original dates kept; Jane is named without her address."""
        self.write(*self.archive())
        output = self.run_import()
        self.assertIn("Imported 1 topics and 2 replies", output)
        topic = Discussion.objects.get(title="Indicia dates")
        first, reply, thanks = topic.posts.order_by("created_at")
        self.assertEqual(first.author, self.author)
        self.assertEqual(first.content, "*Jane Doe wrote on the email list:*\n\nWhich date?")
        self.assertNotIn("jane@example.net", first.content)
        self.assertEqual((reply.author, reply.content, reply.parent), (self.other, "They differ.", first))
        self.assertIsNone(thanks.parent)
        self.assertEqual(topic.created_at, datetime(2006, 1, 2, 10, tzinfo=timezone.utc))
        self.assertEqual((topic.post_count, topic.last_activity),
                         (3, datetime(2006, 1, 4, 8, tzinfo=timezone.utc)))

    def test_import_notifies_nobody_and_runs_once(self):
        """The import notifies and emails nobody, and a second run skips the messages already imported."""
        self.write(*self.archive())
        self.run_import()
        self.assertIn("Imported 0 topics and 0 replies; skipped 3", self.run_import())
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(OutgoingEmail.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(IncomingEmail.objects.filter(reason="mbox import").count(), 3)

    def test_dry_run_changes_nothing(self):
        """A dry run reports what it would import and leaves no topic or IncomingEmail behind."""
        self.write(*self.archive())
        self.assertIn("Would import 1 topics and 2 replies", self.run_import("--dry-run"))
        self.assertFalse(Discussion.objects.filter(title="Indicia dates").exists())
        self.assertFalse(IncomingEmail.objects.exists())

    def test_forum_copies_and_undated_messages_are_skipped(self):
        """Copies of forum posts sent by the gateway and messages without a date are skipped."""
        self.write(
            self.message("forum@comics.org", "[gcd-main] A forum topic", "Copy", "<forum-post-1@comics.org>",
                         "Mon, 02 Jan 2006 10:00:00 +0000", X_GCD_Forum_Post="1"),
            raw_email("jane@example.net", "gcd-main@googlegroups.com", "No date", "Text", message_id="<d@x>"),
        )
        self.assertIn("Imported 0 topics and 0 replies; skipped 2", self.run_import())
