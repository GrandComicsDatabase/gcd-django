"""Email gateway: each group works as a mailing list.

Outgoing posts are queued in OutgoingEmail and sent by the forum_mail command.
Incoming mail is read from an IMAP mailbox by the same command. Addresses use
plus addressing on FORUM_EMAIL_ADDRESS (default forum@comics.org):

- forum+g-<group slug>@domain starts a topic in that group;
- forum+r-<user id>-<topic id>-<signature>@domain replies to a topic.

The signature makes a reply address valid for one user and one topic only.
"""
import hashlib
import hmac
import imaplib
import logging
import re
from email import message_from_bytes, policy
from email.utils import formataddr, getaddresses, parseaddr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.html import strip_tags

from .models import (
    Discussion, GroupEmailSubscription, IncomingEmail, OutgoingEmail, Post, TopicSubscription,
)

logger = logging.getLogger(__name__)

# Posts that arrive by email have no client IP; this placeholder marks them.
EMAIL_IP = "0.0.0.0"
MAX_ATTEMPTS = 5


def forum_address():
    return getattr(settings, "FORUM_EMAIL_ADDRESS", "forum@comics.org")


def _address(tag):
    local, domain = forum_address().split("@")
    return f"{local}+{tag}@{domain}"


def _signature(*values):
    message = "-".join(str(value) for value in values)
    return salted_hmac("forum-email", message).hexdigest()[:24]


def group_address(category):
    return _address(f"g-{category.slug}")


def reply_address(user, discussion):
    return _address(f"r-{user.pk}-{discussion.pk}-{_signature('reply', user.pk, discussion.pk)}")


def unsubscribe_url(user, kind, object_id):
    path = reverse("forum:email-unsubscribe", args=[
        user.pk, kind, object_id, _signature("unsubscribe", user.pk, kind, object_id)])
    return settings.SITE_URL.rstrip("/") + path


def valid_unsubscribe(user_id, kind, object_id, signature):
    return hmac.compare_digest(_signature("unsubscribe", user_id, kind, object_id), signature)


def message_id(post):
    return f"<forum-post-{post.pk}@{forum_address().split('@')[1]}>"


# Outgoing ------------------------------------------------------------------

def queue_post(post):
    """Queue the post for followers of the topic and email members of the group."""
    from .access import accessible_discussions

    discussion = post.discussion
    users = set(TopicSubscription.objects.filter(discussion=discussion).values_list("user_id", flat=True))
    users |= set(GroupEmailSubscription.objects.filter(category_id=discussion.category_id)
                 .values_list("user_id", flat=True))
    users.discard(post.author_id)
    recipients = [user for user in get_user_model().objects.filter(pk__in=users, is_active=True)
                  if user.email and accessible_discussions(user).filter(pk=discussion.pk).exists()]
    OutgoingEmail.objects.bulk_create(
        [OutgoingEmail(post=post, user=user) for user in recipients], ignore_conflicts=True)


def build_message(post, user):
    discussion = post.discussion
    category = discussion.category
    first = discussion.posts.order_by("pk").first()
    is_first = first is None or first.pk == post.pk
    topic_url = settings.SITE_URL.rstrip("/") + discussion.get_absolute_url()
    if GroupEmailSubscription.objects.filter(user=user, category=category).exists():
        unsubscribe = unsubscribe_url(user, "group", category.pk)
        stop_text = f"Stop emails from {category.name}"
    else:
        unsubscribe = unsubscribe_url(user, "topic", discussion.pk)
        stop_text = "Stop emails about this topic"
    body = (f"{post.author.username} wrote:\n\n{post.content}\n\n-- \n"
            f"Reply to this email to answer, or read the topic: {topic_url}#post-{post.pk}\n"
            f"{stop_text}: {unsubscribe}\n")
    headers = {
        "Message-ID": message_id(post),
        "List-Id": f"{category.name} <{category.slug}.{forum_address().split('@')[1]}>",
        "List-Post": f"<mailto:{group_address(category)}>",
        "List-Unsubscribe": f"<{unsubscribe}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        "Precedence": "list",
        "X-GCD-Forum-Post": str(post.pk),
    }
    if not is_first:
        parent = post.parent or first
        headers["In-Reply-To"] = message_id(parent)
        headers["References"] = " ".join(dict.fromkeys([message_id(first), message_id(parent)]))
    return EmailMessage(
        subject=f"[{category.name}] {'' if is_first else 'Re: '}{discussion.title}",
        body=body,
        from_email=formataddr((f"{post.author.username} via GCD Forum", forum_address())),
        to=[user.email],
        reply_to=[reply_address(user, discussion)],
        headers=headers,
    )


def send_pending(limit=500):
    """Send queued emails; failures are retried on the next run up to MAX_ATTEMPTS."""
    pending = (OutgoingEmail.objects.filter(sent_at=None, attempts__lt=MAX_ATTEMPTS)
               .select_related("post__author", "post__discussion__category", "user")[:limit])
    sent = 0
    with get_connection() as connection:
        for item in pending:
            item.attempts += 1
            try:
                message = build_message(item.post, item.user)
                message.connection = connection
                message.send()
            except Exception as error:  # noqa: BLE001 - keep sending the rest of the queue
                item.error = str(error)[:1000]
                item.save(update_fields=("attempts", "error"))
                logger.warning("Forum email %s failed: %s", item.pk, error)
                continue
            item.sent_at = timezone.now()
            item.error = ""
            item.save(update_fields=("attempts", "error", "sent_at"))
            sent += 1
    return sent


# Incoming ------------------------------------------------------------------

QUOTE_HEADER = re.compile(
    r"^\s*(On .+ wrote:|Il giorno .+ ha scritto:|Am .+ schrieb .+:|Le .+ a écrit\s?:|"
    r"El .+ escribió:|Op .+ schreef .+:|Den .+ skrev .+:|-+\s*Original Message\s*-+|"
    r"-+\s*Messaggio originale\s*-+)\s*$", re.IGNORECASE)
REPLY_PREFIX = re.compile(r"^\s*((re|r|aw|sv|vs|fw|fwd|i|wg|tr)\s*:\s*)+", re.IGNORECASE)


def trim_reply(text):
    """Keep only the new text: drop the quoted message and the signature (RFC 3676)."""
    lines = text.replace("\r\n", "\n").split("\n")
    kept = []
    for index, line in enumerate(lines):
        joined = line + " " + lines[index + 1] if index + 1 < len(lines) else line
        if QUOTE_HEADER.match(line) or (line.startswith("On ") and QUOTE_HEADER.match(joined)):
            break
        if line in ("-- ", "--"):
            break
        kept.append(line)
    while kept and (not kept[-1].strip() or kept[-1].startswith(">")):
        kept.pop()
    return "\n".join(kept).strip()


def _body_text(message):
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    return strip_tags(text) if part.get_content_type() == "text/html" else text


def _forum_recipient(message):
    local, domain = forum_address().lower().split("@")
    headers = ("Delivered-To", "X-Original-To", "To", "Cc")
    for name, address in getaddresses([value for header in headers for value in message.get_all(header, [])]):
        address = address.lower()
        if address.endswith("@" + domain) and address.split("@")[0].startswith(local + "+"):
            return address.split("@")[0][len(local) + 1:]
    return None


def _dmarc_passed(message):
    authserv = getattr(settings, "FORUM_EMAIL_AUTHSERV_ID", "")
    for header in message.get_all("Authentication-Results", []):
        if authserv and not header.strip().lower().startswith(authserv.lower()):
            continue
        return bool(re.search(r"\bdmarc=pass\b", header, re.IGNORECASE))
    return False


def _parent_post(message, discussion):
    domain = re.escape(forum_address().split("@")[1])
    for header in ("In-Reply-To", "References"):
        for match in reversed(re.findall(rf"<forum-post-(\d+)@{domain}>", str(message.get(header, "")))):
            post = Post.objects.filter(pk=int(match), discussion=discussion).first()
            if post:
                return post
    return None


class Rejected(Exception):
    pass


def _reply_target(tag, sender):
    parts = tag[2:].split("-")
    if len(parts) != 3 or not all(parts) or not parts[0].isdigit() or not parts[1].isdigit():
        raise Rejected("malformed reply address")
    user_id, discussion_id, signature = int(parts[0]), int(parts[1]), parts[2]
    if not hmac.compare_digest(_signature("reply", user_id, discussion_id), signature):
        raise Rejected("invalid reply signature")
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or user.email.lower() != sender:
        raise Rejected("sender does not own the reply address")
    return user, discussion_id


def _new_topic_target(tag, sender, message):
    from .access import postable_categories, posting_limit

    if getattr(settings, "FORUM_EMAIL_REQUIRE_DMARC", True) and not _dmarc_passed(message):
        raise Rejected("sender not authenticated (no dmarc=pass)")
    users = list(get_user_model().objects.filter(email__iexact=sender, is_active=True)[:2])
    if len(users) != 1:
        raise Rejected("no single GCD account with this email")
    category = postable_categories(users[0]).filter(slug=tag[2:]).first()
    if category is None:
        raise Rejected("unknown group or no permission to post")
    limit = posting_limit(users[0], new_topic=True)
    if limit:
        raise Rejected(limit)
    return users[0], category


def _create_post(user, discussion, content, parent=None):
    from .access import posting_limit
    from .activity import follow, notify_followers
    from .audit import request_audit

    limit = posting_limit(user)
    if limit:
        raise Rejected(limit)
    token = request_audit.set((user.pk, None))
    try:
        post = Post.objects.create(
            discussion=discussion, author=user, content=content, parent=parent,
            created_by=user, updated_by=user, ip_address=EMAIL_IP)
    finally:
        request_audit.reset(token)
    follow(user, discussion)
    notify_followers(post)
    queue_post(post)
    return post


def process_message(raw):
    """Turn one raw email into a post. Returns the IncomingEmail record."""
    from .access import accessible_discussions

    message = message_from_bytes(raw, policy=policy.default)
    msg_id = (str(message.get("Message-ID", "")).strip()[:255]
              or f"<no-id-{hashlib.sha256(raw).hexdigest()}>")
    existing = IncomingEmail.objects.filter(message_id=msg_id).first()
    if existing:
        return existing
    sender = parseaddr(str(message.get("From", "")))[1].lower()
    tag = _forum_recipient(message)
    record = IncomingEmail(message_id=msg_id, sender=sender[:255], recipient=(tag or "")[:255],
                           subject=str(message.get("Subject", ""))[:255])
    auto = str(message.get("Auto-Submitted", "no")).strip().lower()
    if auto != "no" or str(message.get("Precedence", "")).lower() in ("bulk", "junk") \
            or message.get("X-GCD-Forum-Post"):
        record.status, record.reason = IncomingEmail.Status.IGNORED, "automatic message"
        record.save()
        return record
    try:
        content = trim_reply(_body_text(message))
        if not content:
            raise Rejected("empty message")
        with transaction.atomic():
            if tag and tag.startswith("r-"):
                user, discussion_id = _reply_target(tag, sender)
                discussion = accessible_discussions(user).select_related("category").filter(
                    pk=discussion_id).first()
                if discussion is None or discussion.is_locked or \
                        discussion.status == Discussion.Status.ARCHIVED or \
                        not discussion.category.can_post(user):
                    raise Rejected("topic closed or no permission to reply")
                record.post = _create_post(user, discussion, content, _parent_post(message, discussion))
            elif tag and tag.startswith("g-"):
                user, category = _new_topic_target(tag, sender, message)
                title = REPLY_PREFIX.sub("", record.subject).strip()[:200] or "(no subject)"
                discussion = Discussion.objects.create(
                    title=title, category=category, author=user,
                    created_by=user, updated_by=user, ip_address=EMAIL_IP)
                record.post = _create_post(user, discussion, content)
            else:
                raise Rejected("not addressed to the forum")
            record.status = IncomingEmail.Status.ACCEPTED
            record.save()
    except Rejected as reason:
        record.status, record.reason = IncomingEmail.Status.REJECTED, str(reason)
        record.save()
        # Answer only authenticated senders, so forged senders get no backscatter.
        if sender and _dmarc_passed(message):
            _send_rejection(sender, record)
    return record


def _send_rejection(sender, record):
    forum_url = settings.SITE_URL.rstrip("/") + reverse("forum:index")
    text = (f'Your message "{record.subject}" was not posted to the GCD forum: {record.reason}.\n\n'
            "The forum accepts email from GCD accounts only, from the address of the account. "
            f"Register or sign in at {forum_url}\n")
    EmailMessage(subject=f"Not posted: {record.subject}"[:200], body=text, from_email=forum_address(),
                 to=[sender], headers={"Auto-Submitted": "auto-replied"}).send(fail_silently=True)


def fetch_mailbox():
    """Read unseen messages from FORUM_EMAIL_IMAP and process them."""
    config = getattr(settings, "FORUM_EMAIL_IMAP", None)
    if not config:
        return []
    client_class = imaplib.IMAP4_SSL if config.get("ssl", True) else imaplib.IMAP4
    records = []
    with client_class(config["host"], config.get("port", 993 if config.get("ssl", True) else 143)) as client:
        client.login(config["user"], config["password"])
        client.select(config.get("folder", "INBOX"))
        _, data = client.search(None, "UNSEEN")
        for number in data[0].split():
            _, parts = client.fetch(number, "(RFC822)")
            raw = next((part[1] for part in parts if isinstance(part, tuple)), b"")
            try:
                records.append(process_message(raw))
            except Exception:  # noqa: BLE001 - one bad message must not stop the mailbox
                logger.exception("Forum email %s could not be processed", number)
            client.store(number, "+FLAGS", "\\Seen")
    return records
