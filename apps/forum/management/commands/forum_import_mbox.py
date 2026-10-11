"""Import the archive of an email list into a forum group.

Messages are threaded by Message-ID, In-Reply-To and References, like the mbox
importer of Discourse; a reply whose parent is missing joins the topic with the
same subject. Each Message-ID is imported once, so the command can be run again
on a newer export. Imported posts notify nobody and send no email.
"""
import mailbox
import re
from contextlib import nullcontext
from datetime import timezone as dt_timezone
from email import message_from_bytes, policy
from email.utils import parseaddr, parsedate_to_datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.forum.audit import request_audit
from apps.forum.mail import EMAIL_IP, REPLY_PREFIX, _body_text, trim_reply
from apps.forum.models import Category, Discussion, IncomingEmail, Post

REFERENCE = re.compile(r"<[^<>\s]+>")
IMPORTED = "mbox import"


def _date(message):
    try:
        date = parsedate_to_datetime(str(message.get("Date", "")))
    except (TypeError, ValueError):
        return None
    if date is not None and timezone.is_naive(date):
        date = date.replace(tzinfo=dt_timezone.utc)
    return date


class Command(BaseCommand):
    help = "Import an mbox archive of an email list into a forum group."

    def add_arguments(self, parser):
        parser.add_argument("mbox", help="Path of the mbox file")
        parser.add_argument("--group", required=True, help="Slug of the forum group, such as gcd-main")
        parser.add_argument("--archive-user", required=True,
                            help="Username that authors messages from senders without a single GCD account")
        parser.add_argument("--dry-run", action="store_true", help="Count what would be imported, change nothing")

    def handle(self, *args, **options):
        try:
            self.category = Category.objects.get(slug=options["group"])
            self.archive_user = get_user_model().objects.get(username=options["archive_user"])
        except (Category.DoesNotExist, get_user_model().DoesNotExist) as error:
            raise CommandError(error)
        self.list_tag = re.compile(rf"\[{re.escape(self.category.slug)}\]\s*", re.IGNORECASE)
        try:
            box = mailbox.mbox(options["mbox"], create=False)
        except mailbox.NoSuchMailboxError as error:
            raise CommandError(f"No mbox file at {error}")
        # Read the dates first and the messages one at a time, so large archives fit in memory.
        dated, counts = [], {"topics": 0, "replies": 0, "skipped": 0}
        for key in box.iterkeys():
            date = _date(self.parse(box.get_bytes(key)))
            if date is None:
                counts["skipped"] += 1
            else:
                dated.append((date, key))
        dated.sort()
        with transaction.atomic() if options["dry_run"] else nullcontext():
            for date, key in dated:
                with transaction.atomic():
                    counts[self.import_message(self.parse(box.get_bytes(key)), date)] += 1
            if options["dry_run"]:
                transaction.set_rollback(True)
        prefix = "Would import" if options["dry_run"] else "Imported"
        self.stdout.write(f"{prefix} {counts['topics']} topics and {counts['replies']} replies; "
                          f"skipped {counts['skipped']} messages (repeated, empty or undated).")

    @staticmethod
    def parse(raw):
        return message_from_bytes(raw, policy=policy.default)

    def title(self, message):
        subject = REPLY_PREFIX.sub("", self.list_tag.sub("", str(message.get("Subject", ""))))
        return self.list_tag.sub("", subject).strip()[:200] or "(no subject)"

    def author(self, message):
        name, address = parseaddr(str(message.get("From", "")))
        users = list(get_user_model().objects.filter(email__iexact=address, is_active=True)[:2]) \
            if address else []
        if len(users) == 1:
            return users[0], ""
        # Show the name only: the archive is public and addresses stay private.
        return self.archive_user, f"*{name or 'Unknown sender'} wrote on the email list:*\n\n"

    def parent(self, message):
        references = REFERENCE.findall(f"{message.get('References', '')} {message.get('In-Reply-To', '')}")
        for reference in reversed(references):
            found = IncomingEmail.objects.filter(message_id=reference, post__isnull=False).select_related(
                "post__discussion").first()
            if found and found.post.discussion.category_id == self.category.pk:
                return found.post
        return None

    def import_message(self, message, date):
        msg_id = str(message.get("Message-ID", "")).strip()[:255]
        # Copies of forum posts sent by the gateway are already in the forum.
        if not msg_id or message.get("X-GCD-Forum-Post") or \
                IncomingEmail.objects.filter(message_id=msg_id).exists():
            return "skipped"
        sender = parseaddr(str(message.get("From", "")))[1].lower()[:255]
        record = IncomingEmail(message_id=msg_id, sender=sender, recipient=f"g-{self.category.slug}"[:255],
                               subject=str(message.get("Subject", ""))[:255])
        content = trim_reply(_body_text(message))
        if not content:
            record.status, record.reason = IncomingEmail.Status.IGNORED, "empty message (mbox import)"
            record.save()
            return "skipped"
        user, header = self.author(message)
        parent = self.parent(message)
        discussion = parent.discussion if parent else None
        is_reply = bool(REFERENCE.search(str(message.get("In-Reply-To", "")) + str(message.get("References", "")))
                        or REPLY_PREFIX.match(self.list_tag.sub("", str(message.get("Subject", "")))))
        if discussion is None and is_reply:
            imported = IncomingEmail.objects.filter(reason=IMPORTED).values("post__discussion")
            discussion = Discussion.objects.filter(
                category=self.category, title=self.title(message), pk__in=imported).order_by("-created_at").first()
        token = request_audit.set((self.archive_user.pk, None))
        try:
            created = discussion is None
            if created:
                discussion = Discussion.objects.create(
                    title=self.title(message), category=self.category, author=user,
                    created_by=user, updated_by=user, ip_address=EMAIL_IP)
                Discussion.all_objects.filter(pk=discussion.pk).update(created_at=date, updated_at=date)
            post = Post.objects.create(discussion=discussion, author=user, content=header + content, parent=parent,
                                       created_by=user, updated_by=user, ip_address=EMAIL_IP)
        finally:
            request_audit.reset(token)
        Post.all_objects.filter(pk=post.pk).update(created_at=date, updated_at=date)
        discussion.update_counters()
        record.status, record.reason, record.post = IncomingEmail.Status.ACCEPTED, IMPORTED, post
        record.save()
        return "topics" if created else "replies"
