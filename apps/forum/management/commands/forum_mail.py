from django.core.management.base import BaseCommand

from apps.forum.mail import fetch_mailbox, send_pending


class Command(BaseCommand):
    help = "Read the forum mailbox into posts, then send the queued forum emails. Run it from cron."

    def add_arguments(self, parser):
        parser.add_argument("--no-fetch", action="store_true", help="Do not read the mailbox.")
        parser.add_argument("--no-send", action="store_true", help="Do not send queued emails.")

    def handle(self, *args, **options):
        if not options["no_fetch"]:
            records = fetch_mailbox()
            accepted = sum(record.status == "accepted" for record in records)
            self.stdout.write(f"Read {len(records)} messages, {accepted} posted.")
        if not options["no_send"]:
            self.stdout.write(f"Sent {send_pending()} emails.")
