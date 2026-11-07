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
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.html import strip_tags

from .models import (
    Discussion, GroupEmailSubscription, IncomingEmail, OutgoingEmail, Post, RecordSubscription,
    TopicSubscription,
)
from .utils import display_name, to_id

logger = logging.getLogger(__name__)

# Posts that arrive by email have no client IP; this placeholder marks them.
EMAIL_IP = "0.0.0.0"
MAX_ATTEMPTS = 5
# Seconds before a mail server that stopped answering fails the step, so one cron run never hangs.
TIMEOUT = 60
WITHDRAWN = "Withdrawn: the post was removed, or the recipient can no longer read its topic."


def forum_address():
    """FORUM_EMAIL_ADDRESS, by default forum@comics.org; group and reply addresses add a plus tag to it."""
    return getattr(settings, "FORUM_EMAIL_ADDRESS", "forum@comics.org")


def _address(tag):
    """The forum address with the tag after a plus sign: forum+<tag>@domain."""
    local, domain = forum_address().split("@")
    return f"{local}+{tag}@{domain}"


def _signature(*values):
    """A 24-character HMAC of the values with SECRET_KEY, so signed addresses and links cannot be forged."""
    message = "-".join(str(value) for value in values)
    return salted_hmac("forum-email", message).hexdigest()[:24]


def group_address(category):
    """The address that starts a topic in the group by email: forum+g-<slug>@domain."""
    return _address(f"g-{category.slug}")


def reply_address(user, discussion):
    """The address where the user replies to the topic, signed so it works for that user and topic only."""
    return _address(f"r-{user.pk}-{discussion.pk}-{_signature('reply', user.pk, discussion.pk)}")


def unsubscribe_url(user, kind, object_id):
    """The absolute, signed link where the user stops the emails of a group (kind "group"), unfollows a
    topic (kind "topic") or stops following a record (kind "record", with the RecordSubscription id)."""
    path = reverse("forum:email-unsubscribe", args=[
        user.pk, kind, object_id, _signature("unsubscribe", user.pk, kind, object_id)])
    return settings.SITE_URL.rstrip("/") + path


def valid_unsubscribe(user_id, kind, object_id, signature):
    """Whether an unsubscribe link's signature matches its user, kind and object, in constant time."""
    return hmac.compare_digest(_signature("unsubscribe", user_id, kind, object_id).encode(),
                               str(signature).encode())


def message_id(post):
    """The Message-ID of the post's emails; replies that cite it are threaded under the post."""
    return f"<forum-post-{post.pk}@{forum_address().split('@')[1]}>"


# Outgoing ------------------------------------------------------------------

def queue_post(post, extra_users=()):
    """Queue the post for followers of the topic, email members of the group and extra users who can read
    it (access.readers, a few queries for any number of them)."""
    from .access import readers

    discussion = post.discussion
    users = set(TopicSubscription.objects.filter(discussion=discussion).values_list("user_id", flat=True))
    users |= set(GroupEmailSubscription.objects.filter(
        category_id=discussion.category_id, mode=GroupEmailSubscription.Mode.EACH).values_list("user_id", flat=True))
    users |= {user.pk for user in extra_users}
    users.discard(post.author_id)
    allowed = readers(discussion, users)
    recipients = [user for user in get_user_model().objects.filter(pk__in=allowed) if user.email]
    OutgoingEmail.objects.bulk_create(
        [OutgoingEmail(post=post, user=user) for user in recipients], ignore_conflicts=True)


def build_message(post, user):
    """The email of a post for one user: list and threading headers, the user's own reply address, links to
    the files, and a footer with the post's page and the link that stops these emails."""
    discussion = post.discussion
    category = discussion.category
    first = discussion.posts.order_by("pk").first()
    is_first = first is None or first.pk == post.pk
    post_url = settings.SITE_URL.rstrip("/") + post.get_absolute_url()
    record_follow = None
    if not TopicSubscription.objects.filter(user=user, discussion=discussion).exists():
        match = Q()
        for link in discussion.records.all():
            match |= Q(content_type_id=link.content_type_id, object_id=link.object_id)
        record_follow = RecordSubscription.objects.filter(match, user=user).first() if match else None
    if GroupEmailSubscription.objects.filter(
            user=user, category=category, mode=GroupEmailSubscription.Mode.EACH).exists():
        unsubscribe = unsubscribe_url(user, "group", category.pk)
        stop_text = f"Stop emails from {category.name}"
    elif record_follow is not None:
        # Sent because the user follows a record the topic is about (activity.notify_record_followers).
        unsubscribe = unsubscribe_url(user, "record", record_follow.pk)
        stop_text = "Stop following the record"
    else:
        unsubscribe = unsubscribe_url(user, "topic", discussion.pk)
        stop_text = "Stop emails about this topic"
    files = "".join(f"Attached: {item.name} {settings.SITE_URL.rstrip('/')}{item.get_absolute_url()}\n"
                    for item in post.attachments.all())
    if files:
        files += "\n"
    body = (f"{display_name(post.author)} wrote:\n\n{post.content}\n\n{files}-- \n"
            f"Reply to this email to answer, or read the topic: {post_url}\n"
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
        from_email=formataddr((f"{display_name(post.author)} via GCD Forum", forum_address())),
        to=[user.email],
        reply_to=[reply_address(user, discussion)],
        headers=headers,
    )


def readable(item):
    """Whether the queued post may still go to its recipient: the post and its topic are published, not
    removed, and the recipient is active and can still read the topic (it may have moved to another group)."""
    from .access import accessible_posts

    return item.user.is_active and accessible_posts(item.user).filter(pk=item.post_id).exists()


def send_pending(limit=500):
    """Send queued emails; failures are retried on the next run up to MAX_ATTEMPTS.

    Each email is checked again just before it is sent: a post removed, held or moved out of the
    recipient's reach since it was queued is withdrawn (no more attempts, error WITHDRAWN), not sent.
    """
    pending = (OutgoingEmail.objects.filter(sent_at=None, attempts__lt=MAX_ATTEMPTS)
               .select_related("post__author__indexer", "post__discussion__category", "user")[:limit])
    sent = withdrawn = 0
    with get_connection(timeout=TIMEOUT) as connection:
        for item in pending:
            if not readable(item):
                item.attempts, item.error = MAX_ATTEMPTS, WITHDRAWN
                item.save(update_fields=("attempts", "error"))
                withdrawn += 1
                continue
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
    if withdrawn:
        logger.info("Forum: %s queued emails withdrawn, their posts removed or out of reach", withdrawn)
    return sent


DIGEST_DAYS = 7
DIGEST_TOPICS = 30


def build_digest(subscription, since):
    """The weekly summary of a group: topics with posts since the last summary."""
    from .access import accessible_discussions

    user, category = subscription.user, subscription.category
    topics = list(accessible_discussions(user).filter(category=category, last_activity__gt=since)
                  .order_by("-last_activity")[:DIGEST_TOPICS])
    if not topics:
        return None
    site = settings.SITE_URL.rstrip("/")
    lines = [f"New in {category.name} since {since:%Y-%m-%d}:", ""]
    for topic in topics:
        new = topic.posts.filter(created_at__gt=since).count()
        started = " (new topic)" if topic.created_at > since else ""
        lines.append(f"- {topic.title}{started}: {new} new post{'s' if new != 1 else ''}")
        lines.append(f"  {site}{topic.get_absolute_url()}")
    unsubscribe = unsubscribe_url(user, "group", category.pk)
    lines += ["", "-- ", f"Stop these summaries: {unsubscribe}"]
    return EmailMessage(
        subject=f"[{category.name}] Weekly summary", body="\n".join(lines),
        from_email=formataddr(("GCD Forum", forum_address())), to=[user.email],
        headers={
            "List-Id": f"{category.name} <{category.slug}.{forum_address().split('@')[1]}>",
            "List-Unsubscribe": f"<{unsubscribe}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "Precedence": "list",
            "Auto-Submitted": "auto-generated",
        },
    )


def send_digests():
    """Send the weekly summaries that are due; run it daily or more often."""
    now = timezone.now()
    due = (GroupEmailSubscription.objects.filter(mode=GroupEmailSubscription.Mode.WEEKLY, user__is_active=True)
           .exclude(user__email="").select_related("user", "category"))
    sent = 0
    with get_connection(timeout=TIMEOUT) as connection:
        for subscription in due:
            since = subscription.last_digest_at or subscription.created_at
            if now - since < timezone.timedelta(days=DIGEST_DAYS):
                continue
            message = build_digest(subscription, since)
            if message is not None:
                message.connection = connection
                try:
                    message.send()
                except Exception as error:  # noqa: BLE001 - try again on the next run
                    logger.warning("Forum summary for %s failed: %s", subscription.user_id, error)
                    continue
                sent += 1
            subscription.last_digest_at = now
            subscription.save(update_fields=("last_digest_at",))
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
    """The text of the email: its plain part, else its HTML part without tags; empty when it has neither."""
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    return strip_tags(text) if part.get_content_type() == "text/html" else text


# Images in a signature, such as a logo, come inline and small; scans are larger.
SIGNATURE_IMAGE_SIZE = 20 * 1024


def _attachments(message):
    """The images and PDFs of the email, checked; and a note for each one left out."""
    from django.core.exceptions import ValidationError

    from .attachments import MAX_FILES, detect

    files, notes = [], []
    for part in message.walk():
        if part.is_multipart() or part.get_content_maintype() not in ("image", "application"):
            continue
        name = part.get_filename() or ""
        data = part.get_payload(decode=True) or b""
        if part.get("Content-ID") and part.get_content_maintype() == "image" and len(data) < SIGNATURE_IMAGE_SIZE:
            continue
        try:
            kind = detect(data)
        except ValidationError as error:
            notes.append(f"_The attachment “{name or part.get_content_type()}” was not kept: {error.message}._")
            continue
        if len(files) == MAX_FILES:
            notes.append(f"_The attachment “{name}” was not kept: at most {MAX_FILES} files per post._")
            continue
        files.append((name, data, kind))
    return files, notes


def _forum_recipient(message):
    """The plus tag of the first forum address in Delivered-To, X-Original-To, To or Cc, or None."""
    local, domain = forum_address().lower().split("@")
    headers = ("Delivered-To", "X-Original-To", "To", "Cc")
    for name, address in getaddresses([value for header in headers for value in message.get_all(header, [])]):
        address = address.lower()
        if address.endswith("@" + domain) and address.split("@")[0].startswith(local + "+"):
            return address.split("@")[0][len(local) + 1:]
    return None


def _dmarc_passed(message):
    """Whether the first Authentication-Results header says dmarc=pass; when FORUM_EMAIL_AUTHSERV_ID is set,
    only headers from that server count."""
    authserv = getattr(settings, "FORUM_EMAIL_AUTHSERV_ID", "")
    for header in message.get_all("Authentication-Results", []):
        if authserv and not header.strip().lower().startswith(authserv.lower()):
            continue
        return bool(re.search(r"\bdmarc=pass\b", header, re.IGNORECASE))
    return False


def _parent_post(message, discussion):
    """The topic's post the email answers: the last one named in In-Reply-To, else in References, or None."""
    domain = re.escape(forum_address().split("@")[1])
    for header in ("In-Reply-To", "References"):
        for match in reversed(re.findall(rf"<forum-post-(\d+)@{domain}>", str(message.get(header, "")))):
            post = Post.objects.filter(pk=int(match), discussion=discussion).first()
            if post:
                return post
    return None


class Rejected(Exception):
    """Why an incoming email is not posted; the reason is stored and sent back to authenticated senders."""

    pass


def _reply_target(tag, sender):
    """The user and topic id of a reply tag; raises Rejected if the tag is malformed or wrongly signed, or
    if the user it names is not active or has another address than the sender."""
    parts = tag[2:].split("-")
    if len(parts) != 3 or not all(parts) or to_id(parts[0]) is None or to_id(parts[1]) is None:
        raise Rejected("malformed reply address")
    user_id, discussion_id, signature = to_id(parts[0]), to_id(parts[1]), parts[2]
    if not hmac.compare_digest(_signature("reply", user_id, discussion_id).encode(), signature.encode()):
        raise Rejected("invalid reply signature")
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or user.email.lower() != sender:
        raise Rejected("sender does not own the reply address")
    return user, discussion_id


def _new_topic_target(tag, sender, message):
    """The user and group of a group tag; raises Rejected unless the sender has exactly one active account,
    can post in the group, is under the daily limits and, while FORUM_EMAIL_REQUIRE_DMARC is on (the default),
    passes DMARC."""
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


def _create_post(user, discussion, content, parent=None, files=()):
    """Create the post of an email as the user, or raise Rejected at the daily limit, for a text over
    MAX_CONTENT or when its files cannot be stored; it waits for review when its topic does or a web post
    would, else it is published; its revision records the user and no IP."""
    from .access import needs_review, notify_review, posting_limit
    from .activity import publish
    from .attachments import StoreFailed, save_attachments
    from .audit import request_audit
    from .forms import MAX_CONTENT

    if len(content) > MAX_CONTENT:
        raise Rejected(f"message longer than {MAX_CONTENT:,} characters")
    limit = posting_limit(user)
    if limit:
        raise Rejected(limit)
    token = request_audit.set((user.pk, None))
    try:
        post = Post.objects.create(
            discussion=discussion, author=user, content=content, parent=parent,
            created_by=user, updated_by=user, ip_address=EMAIL_IP,
            awaiting_review=discussion.awaiting_review or needs_review(user, discussion.category))
    finally:
        request_audit.reset(token)
    try:
        save_attachments(post, files)
    except StoreFailed:
        raise Rejected("the attached files could not be stored; send the message again later") from None
    if post.awaiting_review:
        notify_review(post)
    else:
        publish(post)
    return post


def process_message(raw):
    """Turn one raw email into a post. Returns the IncomingEmail record."""
    from .access import accessible_discussions
    from .attachments import files_kept_if_committed

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
        files, notes = _attachments(message)
        content = "\n\n".join([trim_reply(_body_text(message)), *notes]).strip()
        if not content and not files:
            raise Rejected("empty message")
        # Files stored for a message whose post is then rolled back are deleted with it.
        with files_kept_if_committed(), transaction.atomic():
            if tag and tag.startswith("r-"):
                user, discussion_id = _reply_target(tag, sender)
                discussion = accessible_discussions(user).select_related("category").filter(
                    pk=discussion_id).first()
                if discussion is None or discussion.is_locked or \
                        discussion.status == Discussion.Status.ARCHIVED or \
                        not discussion.category.can_post(user):
                    raise Rejected("topic closed or no permission to reply")
                record.post = _create_post(user, discussion, content, _parent_post(message, discussion), files)
            elif tag and tag.startswith("g-"):
                from .access import needs_review

                user, category = _new_topic_target(tag, sender, message)
                title = REPLY_PREFIX.sub("", record.subject).strip()[:200] or "(no subject)"
                discussion = Discussion.objects.create(
                    title=title, category=category, author=user,
                    created_by=user, updated_by=user, ip_address=EMAIL_IP,
                    awaiting_review=needs_review(user, category))
                record.post = _create_post(user, discussion, content, files=files)
            else:
                raise Rejected("not addressed to the forum")
            record.status = IncomingEmail.Status.ACCEPTED
            if record.post.awaiting_review:
                record.reason = "awaiting review by a moderator"
            record.save()
    except Rejected as reason:
        record.status, record.reason = IncomingEmail.Status.REJECTED, str(reason)
        record.save()
        # Answer only authenticated senders, so forged senders get no backscatter.
        if sender and _dmarc_passed(message):
            _send_rejection(sender, record)
    return record


def _send_rejection(sender, record):
    """Tell the sender why the email was not posted and where to sign in; a sending error is logged."""
    forum_url = settings.SITE_URL.rstrip("/") + reverse("forum:index")
    text = (f'Your message "{record.subject}" was not posted to the GCD forum: {record.reason}.\n\n'
            "The forum accepts email from GCD accounts only, from the address of the account. "
            f"Register or sign in at {forum_url}\n")
    try:
        EmailMessage(subject=f"Not posted: {record.subject}"[:200], body=text, from_email=forum_address(),
                     to=[sender], headers={"Auto-Submitted": "auto-replied"},
                     connection=get_connection(timeout=TIMEOUT)).send()
    except Exception:  # noqa: BLE001 - the email is already recorded as rejected
        logger.exception("Forum: the rejection notice for %s could not be sent", record.message_id)


def fetch_mailbox():
    """Read unseen messages from FORUM_EMAIL_IMAP and process them. A server that refuses the folder or the
    search, or stops answering for TIMEOUT seconds, raises imaplib.IMAP4.error or OSError."""
    config = getattr(settings, "FORUM_EMAIL_IMAP", None)
    if not config:
        return []
    client_class = imaplib.IMAP4_SSL if config.get("ssl", True) else imaplib.IMAP4
    records = []
    port = config.get("port", 993 if config.get("ssl", True) else 143)
    with client_class(config["host"], port, timeout=TIMEOUT) as client:
        client.login(config["user"], config["password"])
        folder = config.get("folder", "INBOX")
        status, data = client.select(folder)
        if status != "OK":
            raise imaplib.IMAP4.error(f"cannot open the folder {folder}: {data}")
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            raise imaplib.IMAP4.error(f"cannot search the folder {folder}: {data}")
        for number in data[0].split():
            _, parts = client.fetch(number, "(RFC822)")
            raw = next((part[1] for part in parts if isinstance(part, tuple)), b"")
            try:
                records.append(process_message(raw))
            except Exception:  # noqa: BLE001 - one bad message must not stop the mailbox
                logger.exception("Forum email %s could not be processed", number)
            client.store(number, "+FLAGS", "\\Seen")
    return records
