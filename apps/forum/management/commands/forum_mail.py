import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.forum.activity import check_all_fixes
from apps.forum.mail import fetch_mailbox, send_digests, send_pending

logger = logging.getLogger(__name__)


def lock_name():
    """The MySQL named lock held while a run works, so a run that starts before the last one ended stops at
    once. Named locks are shared by the whole server: the name carries the database's, so sites on one
    server (production and beta, parallel test databases) do not stop each other's runs."""
    return f"gcd_forum_mail.{connection.settings_dict['NAME']}"[:64]


class Command(BaseCommand):
    """Forum cron job: read the mailbox, mark fixed topics, send queued emails and due weekly summaries."""

    help = ("Read the forum mailbox into posts, mark topics fixed by approved database changes, "
            "then send the queued forum emails and the weekly summaries that are due. Run it from cron.")

    def add_arguments(self, parser):
        """--no-fetch leaves the mailbox unread and --no-send sends no email; the fix check always runs."""
        parser.add_argument("--no-fetch", action="store_true", help="Do not read the mailbox.")
        parser.add_argument("--no-send", action="store_true", help="Do not send emails.")

    def handle(self, *args, **options):
        """Run the steps one after the other, each on its own: a step that fails is logged and the next ones
        still run, and the command then ends with an error naming the failed steps. A run that finds
        another one still working stops without doing anything."""
        if not self.lock():
            self.stdout.write("Another forum_mail run is still working; this one stops.")
            return
        try:
            steps = []
            if not options["no_fetch"]:
                steps.append(("read the mailbox", self.fetch))
            steps.append(("mark fixed topics", self.fixes))
            if not options["no_send"]:
                steps.append(("send emails", self.send))
            failed = []
            for name, step in steps:
                try:
                    step()
                except Exception:  # noqa: BLE001 - one step failing must not stop the others
                    logger.exception("forum_mail could not %s", name)
                    failed.append(name)
        finally:
            self.unlock()
        if failed:
            raise CommandError(f"forum_mail could not {', '.join(failed)}; see the errors above.")

    def fetch(self):
        """Read the mailbox and print how many messages were read and posted."""
        records = fetch_mailbox()
        accepted = sum(record.status == "accepted" for record in records)
        self.stdout.write(f"Read {len(records)} messages, {accepted} posted.")

    def fixes(self):
        """Mark the topics fixed by approved database changes and print how many."""
        self.stdout.write(f"Marked {check_all_fixes()} topics fixed by approved changes.")

    def send(self):
        """Send the queued emails and the weekly summaries that are due, and print how many."""
        self.stdout.write(f"Sent {send_pending()} emails and {send_digests()} weekly summaries.")

    def lock(self):
        """Take the run's named lock without waiting; False when another run holds it. Other databases than
        MySQL have no such lock, and runs are not serialized there."""
        if connection.vendor != "mysql":
            return True
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", [lock_name()])
            return cursor.fetchone()[0] == 1

    def unlock(self):
        """Release the run's named lock."""
        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name()])
