import logging
import re

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, Exists, F, OuterRef, Prefetch, Q, Value, When, prefetch_related_objects
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from django.views.generic import CreateView, UpdateView

from .forms import (
    MAX_CONTENT,
    DiscussionEditForm,
    DiscussionForm,
    MoveForm,
    PostEditForm,
    PostForm,
    RecordLinksField,
    ReportForm,
    with_descriptions,
)
from .models import (
    Attachment, Category, ContentRevision, Discussion, DiscussionChange, DiscussionRecord, GroupEmailSubscription,
    Notification, Objection, Poll, PollOption, PollVote, Post, PostVote, RecordSubscription, Report,
    TopicSubscription,
)
from .access import (
    accessible_discussions, accessible_posts, edit_limit, moderated_categories, needs_review, notify_review,
    postable_categories, posting_limit, register_required, visible_categories,
)
from .attachments import StoreFailed, files_follow_transaction, save_attachments
from .records import get_record, record_content_type
from .activity import (
    follow, link_records, mark_read, publish, unread_notifications, visible_notifications, with_unread,
)
from .mail import valid_unsubscribe
from .utils import can_edit, can_moderate, display_name, get_client_ip, to_id

logger = logging.getLogger(__name__)

PAGE_SIZE = 25


def _is_htmx(request):
    """Whether htmx sent the request, as its HX-Request header says."""
    return request.headers.get("HX-Request") == "true"


# What the name of each record type reads besides its own row (its __str__): an issue its series, a
# creator the birth date, a character its language...
NAME_RELATIONS = {"issue": ("series",), "story_arc": ("language",), "creator": ("birth_date",),
                  "character": ("language",), "group": ("language",), "feature": ("language", "feature_type"),
                  "universe": ("verse",)}


def _records_prefetch():
    """The topics' GCD record links with their content types and records: one query for the links and one
    per record type, whatever the number of topics, with what the records' names read (NAME_RELATIONS)."""
    from django.contrib.contenttypes.prefetch import GenericPrefetch

    from .records import RECORD_TYPES, record_model

    # select_related() without fields would follow every foreign key, so types reading none use all().
    records = [record_model(key).objects.select_related(*NAME_RELATIONS[key]) if key in NAME_RELATIONS
               else record_model(key).objects.all() for key in RECORD_TYPES]
    return Prefetch("records", queryset=DiscussionRecord.objects.select_related("content_type").prefetch_related(
        GenericPrefetch("content_object", records)))


def _topics(user):
    """Topics the user can access, with authors, groups and record links loaded for the topic lists."""
    return (accessible_discussions(user).select_related("author__indexer", "category", "moved_from")
            .prefetch_related(_records_prefetch()))


def _add_unread(topics, user):
    """Unread counts for the topics of one page only, so lists stay fast."""
    if not user.is_authenticated:
        return
    unread = {row["pk"]: row for row in with_unread(
        Discussion.objects.filter(pk__in=[topic.pk for topic in topics]), user
    ).values("pk", "last_read_post_id", "unread_count", "first_unread_id")}
    for topic in topics:
        row = unread.get(topic.pk, {})
        topic.last_read_post_id = row.get("last_read_post_id")
        topic.unread_count = row.get("unread_count", 0)
        topic.first_unread_id = row.get("first_unread_id")


def _topic_page(request, queryset):
    """Filter, order and paginate a topic list from the query string."""
    from .search import add_excerpts, search

    query = request.GET.get("q", "").strip()[:200]
    best_posts, notes = {}, []
    if query:
        queryset, best_posts, parsed = search(queryset, query)
        notes = parsed.notes()
    feed = request.GET.get("feed", "latest")
    if feed in ("mine", "following") and not request.user.is_authenticated:
        feed = "latest"
    if feed == "unanswered":
        queryset = queryset.filter(post_count__lte=1)
    elif feed == "mine":
        queryset = queryset.filter(Exists(Post.objects.filter(
            discussion_id=OuterRef("pk"), author=request.user)))
    elif feed == "following":
        queryset = queryset.filter(Exists(TopicSubscription.objects.filter(
            discussion_id=OuterRef("pk"), user=request.user)))
    ordering = ("-created_at",) if feed == "new" else ("-last_activity", "-created_at")
    if not best_posts:
        queryset = queryset.order_by("-is_pinned", *ordering, "-pk")
    # Results of a full-text search keep their order by relevance.
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    _add_unread(page.object_list, request.user)
    if query:
        add_excerpts(page.object_list, best_posts, parsed)
    return {"page_obj": page, "discussions": page.object_list, "search_query": query, "search_notes": notes,
            "active_feed": feed}


def group_sections(categories):
    """Group categories under their Email Lists FAQ section, in section order."""
    sections = []
    for value, title in Category.Section.choices:
        groups = [category for category in categories if category.section == value]
        if groups:
            sections.append({"title": title, "groups": groups})
    return sections


def _awaiting_review(user):
    """Posts of new accounts waiting for a moderator of their group, oldest first."""
    return (Post.all_objects.filter(awaiting_review=True, is_deleted=False,
                                    discussion__category__in=moderated_categories(user))
            .select_related("author__indexer", "discussion__category").prefetch_related("attachments")
            .order_by("created_at"))


def _open_reports(user):
    """Open reports about content in the groups the user moderates."""
    categories = moderated_categories(user)
    posts = Post.all_objects.filter(discussion__category__in=categories).values("pk")
    topics = Discussion.all_objects.filter(category__in=categories).values("pk")
    return Report.objects.filter(status=Report.Status.OPEN).filter(
        Q(content_type=ContentType.objects.get_for_model(Post), object_id__in=posts)
        | Q(content_type=ContentType.objects.get_for_model(Discussion), object_id__in=topics))


def _sidebar(user):
    """The sidebar: groups by section with topic counts, unread notifications and items to moderate."""
    categories = list(visible_categories(user))
    # The topics the user can list: in a group they post in but cannot read (gcd-error), their own.
    counts = {row["category"]: row["topics"] for row in
              accessible_discussions(user).order_by().values("category").annotate(topics=Count("pk"))}
    for category in categories:
        category.topic_count = counts.get(category.pk, 0)
    moderator = user.is_authenticated and moderated_categories(user).exists()
    return {"sections": group_sections(categories),
            "notification_count": unread_notifications(user).count() if user.is_authenticated else 0,
            "is_moderator": moderator,
            "report_count": (_open_reports(user).count() + _awaiting_review(user).count()) if moderator else 0}


@require_safe
def index(request):
    """The forum home page: the topics the user can access, from every group."""
    context = _sidebar(request.user)
    context.update(_topic_page(request, _topics(request.user)))
    return render(request, "forum/index.html", context)


@require_safe
def group(request, slug):
    """A group's page: its topics and those moved away, the user's email setting and the group's agenda."""
    category = get_object_or_404(visible_categories(request.user), slug=slug)
    # Topics moved away stay listed in their old group, pointing to the new one.
    topics = _topics(request.user).filter(Q(category=category) | Q(moved_from=category))
    context = _sidebar(request.user)
    context.update(_topic_page(request, topics))
    subscription = GroupEmailSubscription.objects.filter(
        user=request.user, category=category).first() if request.user.is_authenticated else None
    context.update(_agenda_context(category))
    context.update(category=category, can_post=category.can_post(request.user),
                   can_read=category.can_read(request.user),
                   email_mode=subscription.mode if subscription else "off",
                   email_modes=GroupEmailSubscription.Mode.choices)
    return render(request, "forum/index.html", context)


def _agenda_context(category):
    """Open agenda items and ballots of the group, each with its forum topic, if any."""
    from .procedure import agenda_items_for, agendas_for, open_ballots_for

    if not agendas_for(category).exists():
        return {}
    items = list(agenda_items_for(category))
    ballots = list(open_ballots_for(category))
    topics = Discussion.objects.filter(Q(agenda_item__in=items) | Q(ballot__in=ballots), category=category)
    by_item = {topic.agenda_item_id: topic for topic in topics if topic.agenda_item_id}
    by_ballot = {topic.ballot_id: topic for topic in topics if topic.ballot_id}
    for item in items:
        item.forum_topic = by_item.get(item.pk)
    for ballot in ballots:
        ballot.forum_topic = by_ballot.get(ballot.pk)
    return {"agenda_items": items, "open_ballots": ballots}


@require_safe
def record(request, key, object_id):
    """Topics linked to a GCD record across the groups the user can access, and whether they follow it."""
    found = get_record(key, object_id)
    if found is None:
        raise Http404
    topics = _topics(request.user).filter(
        records__content_type=record_content_type(key), records__object_id=object_id)
    context = _sidebar(request.user)
    context.update(_topic_page(request, topics))
    context.update(record=found, record_key=key, record_following=request.user.is_authenticated and (
        RecordSubscription.objects.filter(user=request.user, content_type=record_content_type(key),
                                          object_id=found.pk).exists()))
    return render(request, "forum/index.html", context)


@login_required
@require_POST
def follow_record(request, key, object_id):
    """Follow a GCD record, or stop: every new topic about it brings a notification and an email.

    The form says which of the two it asks for ("follow" 1 or 0), so a second click sent before the page
    reloads repeats the request instead of undoing it.
    """
    found = get_record(key, object_id)
    if found is None:
        raise Http404
    wanted = request.POST.get("follow")
    if wanted not in ("0", "1"):
        return HttpResponseBadRequest("Say whether to follow the record.")
    fields = {"user": request.user, "content_type": record_content_type(key), "object_id": found.pk}
    if wanted == "1":
        RecordSubscription.objects.get_or_create(**fields)
        messages.success(request, f"You will hear about every new topic about {found}.")
    else:
        RecordSubscription.objects.filter(**fields).delete()
        messages.success(request, f"You no longer follow {found}.")
    return redirect("forum:record", key=key, object_id=found.pk)


# Records a topic can be linked to at once from "Edit title and records"; also bounds the preview's work.
MAX_PICKED = 50


@require_safe
def record_preview(request):
    """Cards of the GCD records a message links to, or of the records picked for a topic."""
    from .records import LINK, records_in_text
    from .templatetags.forum_tags import MAX_CARDS, record_card_list

    field = RecordLinksField(required=False)
    # The message box sends the links of its text ("content"); the records band sends "records".
    picked = "records" in request.GET
    links = "\n".join(LINK.findall(request.GET.get("content", ""))[:MAX_PICKED])
    found, invalid = ([] if picked else records_in_text(links)), []
    lines = list(dict.fromkeys(line.strip() for line in request.GET.get("records", "").splitlines() if line.strip()))
    for line in lines[:MAX_PICKED]:
        try:
            found.extend(field.clean(line))
        except ValidationError:
            invalid.append(line)
    # A message shows as many cards as its post will; picked records are all linked.
    shown = found[:MAX_PICKED] if picked else found[:MAX_CARDS]
    more = len(found) - len(shown) + max(len(lines) - MAX_PICKED, 0)
    return render(request, "forum/_record_preview.html", {
        "cards": record_card_list(shown), "more": more, "picked": picked, "invalid": invalid})


class DiscussionCreateView(LoginRequiredMixin, CreateView):
    """Start a topic with its first post; links from a group, a record or an agenda item preset the form."""

    form_class = DiscussionForm
    template_name = "forum/form.html"

    def get_initial(self):
        """Preset the group, the agenda item and a message linking a GCD record, from the query string."""
        initial = super().get_initial()
        category = postable_categories(self.request.user).filter(
            slug=self.request.GET.get("category", "")).first()
        if category:
            initial["category"] = category.pk
        key, _, object_id = self.request.GET.get("record", "").partition(":")
        found = get_record(key, to_id(object_id)) if to_id(object_id) is not None else None
        if found:
            # The link in the message links the topic to the record.
            label = str(found).replace("[", "").replace("]", "")
            initial["content"] = f"[{label}]({self.request.build_absolute_uri(found.get_absolute_url())})\n\n"
        agenda_item = self.request.GET.get("agenda_item", "")
        if to_id(agenda_item) is not None:
            initial["agenda_item"] = to_id(agenda_item)
        return initial

    def get_form_kwargs(self):
        """Pass the form the author, whose groups and limits it checks, and the IP address it records."""
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, ip_address=get_client_ip(self.request))
        return kwargs

    def form_valid(self, form):
        """Save and open the topic; one that waits for a moderator leads back to its group with a notice.

        If its files cannot be stored, nothing is saved and the form says so.
        """
        try:
            discussion = form.save()
        except StoreFailed as error:
            form.add_error("attachments", str(error))
            return self.form_invalid(form)
        # The next page tells the browser the topic is published, so its draft can go (forum_tags).
        self.request.session["forum_draft_published"] = True
        if discussion.awaiting_review:
            messages.info(self.request, REVIEW_MESSAGE)
            return redirect(discussion.category.get_absolute_url())
        return redirect(discussion.get_absolute_url())


REVIEW_MESSAGE = ("Thank you! The first message of a new member is read by a moderator of the group "
                  "before it appears; you will find it here once approved.")

ROOTS_PER_PAGE = 20


def _post_tree(discussion):
    """Top-level posts with their replies under them, one level deep like GitHub Discussions.

    A reply to a reply stays under the top-level post and says whom it answers.
    """
    posts = list(
        Post.all_objects.filter(discussion=discussion, awaiting_review=False)
        .select_related("author__indexer").prefetch_related("attachments")
        .annotate(vote_count=Count("votes"))
        .order_by("created_at", "pk")
    )
    by_id = {post.pk: post for post in posts}
    roots = []
    for post in posts:
        post.tree_children = []
        post.user_has_voted = False
    for post in posts:
        parent = by_id.get(post.parent_id)
        # Walking up, not by date order: an imported reply can be dated before the post it answers.
        root, seen = post, {post.pk}
        while root.parent_id in by_id and root.parent_id not in seen:
            root = by_id[root.parent_id]
            seen.add(root.pk)
        post.root = root
        if root is post:
            roots.append(post)
        else:
            root.tree_children.append(post)
        post.reply_to = parent if parent is not None and parent is not root else None
    return roots, posts


def _thread_root(post):
    """The top-level post of a post's thread, found by walking up its parents."""
    root = post
    while root.parent_id:
        root = root.parent
    return root


def author_badges(users, category):
    """Roles shown next to author names: staff, board, editors, group moderators, new indexers."""
    from django.contrib.auth.models import Group

    from apps.indexer.models import Indexer

    ids = {user.pk for user in users}
    groups = {}
    for user_id, name in Group.user_set.through.objects.filter(
            user_id__in=ids, group__name__in=("board", "editor")).values_list("user_id", "group__name"):
        groups.setdefault(user_id, set()).add(name)
    moderators = set(category.moderators.filter(pk__in=ids).values_list("pk", flat=True))
    new = set(Indexer.objects.filter(user_id__in=ids, is_new=True).values_list("user_id", flat=True))
    badges = {}
    for user in users:
        names = groups.get(user.pk, set())
        badges[user.pk] = [label for label, has in (
            ("Staff", user.is_staff), ("Board", "board" in names), ("Editor", "editor" in names),
            ("Moderator", user.pk in moderators), ("New indexer", user.pk in new)) if has]
    return badges


def _poll_context(request, discussion):
    """The topic's poll, if any: votes per option, the user's choices, whether they may vote or close it."""
    poll = Poll.objects.filter(discussion=discussion).prefetch_related(
        Prefetch("options", queryset=PollOption.objects.annotate(vote_count=Count("votes")))).first()
    if poll is None:
        return {}
    options = list(poll.options.all())
    voted = set(PollVote.objects.filter(option__poll=poll, user=request.user).values_list(
        "option_id", flat=True)) if request.user.is_authenticated else set()
    voters = PollVote.objects.filter(option__poll=poll).values("user").distinct().count()
    can_vote = (request.user.is_authenticated and poll.is_open()
                and discussion.category.can_post(request.user))
    total = sum(option.vote_count for option in options) or 1
    for option in options:
        option.percent = round(100 * option.vote_count / total)
        option.chosen = option.pk in voted
    return {"poll": poll, "poll_options": options, "poll_voters": voters, "poll_can_vote": can_vote,
            "poll_results": bool(voted) or not can_vote,
            "poll_can_close": poll.is_open() and _can_accept(request.user, discussion)}


# Escapes that keep JSON inert inside a script element, as json_script does.
JSON_SCRIPT_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


def _structured_data(request, discussion, first_post):
    """schema.org data for search engines, for topics anyone can read."""
    import json

    from django.utils.safestring import mark_safe

    if discussion.category.read_access != Category.Access.PUBLIC or first_post is None:
        return None
    return mark_safe(json.dumps({
        "@context": "https://schema.org",
        "@type": "DiscussionForumPosting",
        "headline": discussion.title,
        "url": request.build_absolute_uri(discussion.get_absolute_url()),
        "datePublished": discussion.created_at.isoformat(),
        "author": {"@type": "Person", "name": display_name(discussion.author)},
        "text": first_post.content[:500],
        "commentCount": max(discussion.post_count - 1, 0),
    }).translate(JSON_SCRIPT_ESCAPES))


def _can_reply(user, discussion):
    """Whether the user can reply: the topic is not closed or archived and they can post in its group."""
    return (not discussion.is_locked and discussion.status != Discussion.Status.ARCHIVED
            and discussion.category.can_post(user))


@require_safe
def discussion_detail(request, slug):
    """A topic with its threads of posts, a page at a time; a link to a post opens the page holding it.

    Each session counts one view; a signed-in visit marks the topic and its notifications read.
    """
    if not request.user.is_authenticated and not accessible_discussions(request.user).filter(slug=slug).exists():
        # A link from an email or another site: sign in, then the topic opens. Whether the topic exists is
        # not told, so a visitor cannot probe the titles of members-only groups.
        return register_required(request)
    discussion = get_object_or_404(
        accessible_discussions(request.user).select_related(
            "author__indexer", "category", "moved_from", "moved_by__indexer", "answer__author__indexer",
            "answer__discussion",
        ).prefetch_related(_records_prefetch()),
        slug=slug,
    )
    signed_in = request.user.is_authenticated
    last_read_post_id = mark_read(request.user, discussion) if signed_in else None
    # The topic's own links (first unread post, other pages) carry the mark the reader came with, so the
    # visit that moved it does not hide the posts still unread.
    since = to_id(request.GET.get("since"))
    if since is not None and last_read_post_id is not None:
        last_read_post_id = min(since, last_read_post_id)
    view_key = f"forum-viewed-{discussion.pk}"
    if not request.session.get(view_key):
        # Counted once the request has committed: mark_read's insert holds a shared lock on the topic, and
        # an update here would then deadlock with a reply (see Post.save).
        transaction.on_commit(lambda pk=discussion.pk: Discussion.objects.filter(pk=pk).update(
            views_count=F("views_count") + 1))
        request.session[view_key] = True
        discussion.views_count += 1

    roots, posts = _post_tree(discussion)
    by_id = {post.pk: post for post in posts}
    target = by_id.get(to_id(request.GET.get("post")))
    # "Reply" without scripts: a link that opens the reply form aimed at the post.
    reply_to = by_id.get(to_id(request.GET.get("reply_to")))
    if reply_to is not None and reply_to.is_deleted:
        reply_to = None
    page = Paginator(roots, ROOTS_PER_PAGE).get_page(
        roots.index(target.root) // ROOTS_PER_PAGE + 1 if target else request.GET.get("page"))
    shown = [post for root in page.object_list for post in [root, *root.tree_children]]
    voted_ids = set(PostVote.objects.filter(user=request.user, post__in=shown)
                    .values_list("post_id", flat=True)) if signed_in else set()
    badges = author_badges({post.author for post in shown}, discussion.category)
    first_unread = None
    for post in posts:
        post.user_has_voted = post.pk in voted_ids
        post.badges = badges.get(post.author_id, [])
        post.is_unread = bool(last_read_post_id is not None and post.pk > last_read_post_id
                              and post.author_id != request.user.pk and not post.is_deleted)
        if post.is_unread and first_unread is None:
            first_unread = post
    moderator = can_moderate(request.user, discussion)
    context = {
        "discussion": discussion,
        "post_roots": page.object_list,
        "page_obj": page,
        "reply_form": PostForm(discussion=discussion, initial={"parent": reply_to.pk} if reply_to else None),
        "reply_parent": reply_to,
        "reply_root": reply_to.root if reply_to else None,
        "can_reply": _can_reply(request.user, discussion),
        "can_moderate": moderator,
        "can_edit_topic": can_edit(request.user, discussion),
        # The topic it duplicates, named and linked only for those who can read it.
        "duplicate_of": discussion.duplicate_of_id and accessible_discussions(request.user).filter(
            pk=discussion.duplicate_of_id).first(),
        "can_post": signed_in and discussion.category.can_post(request.user),
        "group_moderator": discussion.category.is_moderator(request.user),
        "can_accept": _can_accept(request.user, discussion),
        "first_post_id": posts[0].pk if posts else None,
        "last_post_id": max(by_id, default=0),
        "first_unread": first_unread,
        "first_unread_here": first_unread is not None and first_unread in shown,
        "read_since": last_read_post_id if first_unread is not None else None,
        "following": signed_in and TopicSubscription.objects.filter(
            user=request.user, discussion=discussion).exists(),
        "move_form": MoveForm(user=request.user, discussion=discussion) if moderator else None,
        "structured_data": _structured_data(
            request, discussion, posts[0] if posts and not posts[0].is_deleted else None),
        "canonical_url": request.build_absolute_uri(discussion.get_absolute_url() + (
            f"?page={page.number}" if page.number > 1 else "")),
    }
    context.update(_poll_context(request, discussion))
    context.update(_database_context(request, discussion))
    context.update(_procedure_context(request, discussion))
    return render(request, "forum/discussion_detail.html", context)


def can_link_change(user, discussion, changeset=None):
    """Topic author, group moderators, editors and staff link changes; indexers link their own changes to
    the topic's records (database.touches_records), not any change to any topic."""
    from .database import touches_records

    if not user.is_authenticated:
        return False
    if (discussion.author_id == user.pk or discussion.category.is_moderator(user)
            or user.groups.filter(name="editor").exists()):
        return True
    return (changeset is not None and changeset.indexer_id == user.pk
            and touches_records(changeset, discussion.records.all()))


def _database_context(request, discussion):
    """Database changes linked to the topic, changes to its records since it started, and experts."""
    from .database import changes_for_records, changeset_state, record_experts

    links = list(discussion.records.all())
    linked = list(DiscussionChange.objects.filter(discussion=discussion).select_related(
        "changeset__indexer__indexer", "linked_by"))
    for item in linked:
        item.state = changeset_state(item.changeset)
    linked_ids = {item.changeset_id for item in linked}
    suggested = [change for change in changes_for_records(links, since=discussion.created_at)
                 if change.pk not in linked_ids] if links else []
    for change in suggested:
        change.state_name = changeset_state(change)
    participants = set(discussion.posts.values_list("author_id", flat=True)) | {request.user.pk}
    return {
        "linked_changes": linked,
        "suggested_changes": suggested,
        "can_link_change": can_link_change(request.user, discussion),
        "experts": record_experts(links, exclude=participants) if links else [],
    }


def _procedure_context(request, discussion):
    """The "Agenda and vote" panel: ballot and consensus state, and what the user may do there."""
    from .procedure import (
        agenda_items_for, agendas_for, ballot_state, can_seek_consensus, consensus_state,
    )

    coordinator = discussion.category.is_moderator(request.user)
    consensus = consensus_state(discussion)
    enabled = agendas_for(discussion.category).exists()
    context = {
        "procedure": enabled or bool(discussion.agenda_item_id or discussion.ballot_id or consensus),
        "coordinator": coordinator,
        "ballot_info": ballot_state(discussion.ballot) if discussion.ballot_id else None,
        "consensus": consensus,
        "can_seek_consensus": enabled and coordinator and can_seek_consensus(discussion),
        "can_object": (consensus is not None and consensus["state"] in ("waiting", "ready")
                       and request.user.is_authenticated and discussion.category.can_post(request.user)),
    }
    if coordinator and enabled:
        choices = list(agenda_items_for(discussion.category))
        if discussion.agenda_item_id and discussion.agenda_item not in choices:
            # A closed item stays linked, so saving the ballot does not drop it.
            choices.insert(0, discussion.agenda_item)
        context["agenda_choices"] = choices
    return context


@require_safe
def discussion_updates(request, slug):
    """Polled by the topic page: tells the reader about replies posted since it loaded."""
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    after = to_id(request.GET.get("after")) or 0
    new = discussion.posts.filter(pk__gt=after)
    if request.user.is_authenticated:
        new = new.exclude(author=request.user)
    first = new.order_by("pk").first()
    if first is None:
        return HttpResponse("")
    # 286 tells htmx to stop polling: the notice is shown once, not announced again every 30 seconds.
    return render(request, "forum/_updates.html", {"count": new.count(), "first": first}, status=286)


def _reply_errors(request, discussion, form):
    """The reply form with its errors (422), still aimed at the post it answers and its thread; htmx puts it
    in place of the old form, and a browser without htmx gets it in a page of the forum."""
    parent = form.cleaned_data.get("parent")
    template = "forum/_reply_form.html" if _is_htmx(request) else "forum/reply_errors.html"
    response = render(request, template, {
        "discussion": discussion, "reply_form": form, "reply_page": request.POST.get("page", ""),
        "reply_parent": parent, "reply_root": _thread_root(parent) if parent else None}, status=422)
    response["HX-Retarget"] = "#reply-form-container"
    response["HX-Reswap"] = "outerHTML"
    return response


@files_follow_transaction
@login_required
@require_POST
def reply(request, slug):
    """Post a reply; htmx gets the new post to insert, or the form with its errors to replace the old one.

    A reply that needs review waits for a moderator, and its author gets a notice instead.
    """
    discussion = get_object_or_404(
        accessible_discussions(request.user).select_related("category"), slug=slug)
    if not _can_reply(request.user, discussion):
        return HttpResponse("You cannot reply to this discussion.", status=403)
    form = PostForm(request.POST, request.FILES, discussion=discussion)
    limit = posting_limit(request.user)
    if limit:
        form.add_error(None, limit)
    if not form.is_valid():
        return _reply_errors(request, discussion, form)

    post = form.save(commit=False)
    post.discussion = discussion
    post.author = request.user
    post.created_by = request.user
    post.updated_by = request.user
    post.ip_address = get_client_ip(request)
    post.awaiting_review = needs_review(request.user, discussion.category)
    try:
        with transaction.atomic():
            post.save()
            save_attachments(post, with_descriptions(form))
    except StoreFailed as error:
        form.add_error("attachments", str(error))
        return _reply_errors(request, discussion, form)
    if post.awaiting_review:
        notify_review(post)
        if _is_htmx(request):
            # Marked, so the page says the reply was sent for review, not posted, and moves the focus here.
            return HttpResponse(f'<p class="mt-2 border border-blue-500 px-2 py-1" role="status" '
                                f'data-held-for-review>{REVIEW_MESSAGE}</p>')
        messages.info(request, REVIEW_MESSAGE)
        return redirect(discussion.get_absolute_url())
    publish(post)
    page = to_id(request.POST.get("page"))
    if _is_htmx(request) and post.parent_id is None and page is not None:
        roots = Post.all_objects.filter(discussion=discussion, parent=None, awaiting_review=False).count()
        if page != (roots - 1) // ROOTS_PER_PAGE + 1:
            response = HttpResponse()
            response["HX-Redirect"] = post.get_absolute_url()
            return response
    if _is_htmx(request):
        post.vote_count = 0
        post.user_has_voted = False
        post.tree_children = []
        post.reply_to = post.parent if post.parent and post.parent.parent_id else None
        post.root = _thread_root(post)
        post.badges = author_badges([request.user], discussion.category)[request.user.pk]
        # The reply made its author follow the topic: the Follow button of the page says so (out of band).
        # Replying needs the right to post, which also lets the author edit the reply.
        html = render_to_string("forum/_post.html", {"post": post, "discussion": discussion, "can_reply": True,
                                                     "can_post": True}, request=request)
        html += render_to_string("forum/_follow_button.html", {"discussion": discussion, "following": True,
                                                               "out_of_band": True}, request=request)
        return HttpResponse(html)
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def toggle_vote(request, pk):
    """Mark a post helpful, or take the vote back; htmx gets the updated button."""
    post = get_object_or_404(accessible_posts(request.user).select_related("discussion"), pk=pk)
    with transaction.atomic():
        vote, created = PostVote.objects.get_or_create(post=post, user=request.user)
        if not created:
            vote.delete()
    post.vote_count = PostVote.objects.filter(post=post).count()
    post.user_has_voted = created
    if _is_htmx(request):
        return render(request, "forum/_vote_button.html", {"post": post})
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def move_discussion(request, slug):
    """Move a topic to another group the user can post in: its author, group moderators and staff."""
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    if not can_edit(request.user, discussion):
        return HttpResponse(status=403)
    form = MoveForm(request.POST, user=request.user, discussion=discussion)
    if not form.is_valid():
        messages.error(request, "Choose a group you can post in.")
        return redirect(discussion.get_absolute_url())
    _lock(discussion)
    discussion.moved_from = discussion.category
    discussion.category = form.cleaned_data["category"]
    discussion.moved_by = request.user
    discussion.moved_at = timezone.now()
    discussion.updated_by = request.user
    discussion.save()
    messages.success(request, f"Moved to {discussion.category}.")
    return redirect(discussion.get_absolute_url())


@login_required
@require_POST
def toggle_follow(request, slug):
    """Follow a topic, or stop following it; htmx gets the updated button.

    The button says which of the two it asks for ("follow" 1 or 0), so a click on a button left stale by a
    reply that followed the topic, or a second click, does what the button says.
    """
    discussion = get_object_or_404(accessible_discussions(request.user), slug=slug)
    wanted = request.POST.get("follow")
    if wanted not in ("0", "1"):
        return HttpResponseBadRequest("Say whether to follow the topic.")
    if wanted == "1":
        follow(request.user, discussion)
    else:
        TopicSubscription.objects.filter(user=request.user, discussion=discussion).delete()
    if _is_htmx(request):
        return render(request, "forum/_follow_button.html", {"discussion": discussion, "following": wanted == "1"})
    return redirect(discussion.get_absolute_url())


@login_required
@require_POST
def group_email(request, slug):
    """Get the posts of a group by email, one by one or in a weekly summary, like a list member."""
    from .access import readable_categories

    category = get_object_or_404(readable_categories(request.user), slug=slug)
    mode = request.POST.get("mode")
    if mode in GroupEmailSubscription.Mode.values:
        GroupEmailSubscription.objects.update_or_create(
            user=request.user, category=category, defaults={"mode": mode})
        label = "every new post" if mode == GroupEmailSubscription.Mode.EACH else "a weekly summary"
        messages.success(request, f"You get {label} of {category.name} at {request.user.email}.")
    else:
        GroupEmailSubscription.objects.filter(user=request.user, category=category).delete()
        messages.success(request, f"You no longer get {category.name} by email.")
    return redirect(category.get_absolute_url())


@csrf_exempt
@require_http_methods(["GET", "POST"])
def email_unsubscribe(request, user_id, kind, object_id, signature):
    """Unsubscribe link of the emails; POST also serves one-click unsubscribe (RFC 8058).

    No session is needed: the signed link identifies the user, so CSRF does not apply.
    """
    if kind not in ("group", "topic", "record") or not valid_unsubscribe(user_id, kind, object_id, signature):
        raise Http404
    if kind == "group":
        subscriptions = GroupEmailSubscription.objects.filter(user_id=user_id, category_id=object_id)
        target = Category.objects.filter(pk=object_id).first()
        about = f"every post of {target.name}" if target else "this group"
    elif kind == "record":
        subscriptions = RecordSubscription.objects.filter(user_id=user_id, pk=object_id)
        target = subscriptions.select_related("content_type").first()
        model = target.content_type.model_class() if target else None
        found = model._default_manager.filter(pk=target.object_id).first() if model else None
        about = f"new topics about {found}" if found else "new topics about this record"
    else:
        subscriptions = TopicSubscription.objects.filter(user_id=user_id, discussion_id=object_id)
        target = Discussion.objects.filter(pk=object_id).first()
        about = f'replies to "{target.title}"' if target else "this topic"
    if request.method == "POST":
        subscriptions.delete()
    return render(request, "forum/unsubscribed.html", {"done": request.method == "POST", "about": about})


@require_safe
def notifications(request):
    """The user's notifications, newest first; reading a topic marks its ones read."""
    items = Paginator(
        visible_notifications(request.user)
        .select_related("post__author__indexer", "post__discussion__category"), PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = _sidebar(request.user)
    context.update(page_obj=items, notifications=items.object_list, active_page="notifications")
    return render(request, "forum/notifications.html", context)


@login_required
@require_POST
def notifications_read(request):
    """Mark all the user's notifications read."""
    unread_notifications(request.user).update(read_at=timezone.now())
    return redirect("forum:notifications")


def _can_accept(user, discussion):
    """Whether the user may pick the answer or close the poll: topic author, group moderators, staff."""
    return discussion.author_id == user.pk or discussion.category.is_moderator(user)


@login_required
@require_POST
def accept_answer(request, pk):
    """Mark a reply as the answer, or unmark it: topic author or group moderators."""
    post = get_object_or_404(accessible_posts(request.user).select_related("discussion__category"), pk=pk)
    discussion = post.discussion
    first_post_id = discussion.posts.order_by("pk").values_list("pk", flat=True).first()
    if not _can_accept(request.user, discussion) or post.pk == first_post_id:
        return HttpResponse(status=403)
    _lock(discussion)
    if discussion.status == Discussion.Status.ARCHIVED:
        messages.error(request, "The topic is archived: its answer can no longer change.")
        return redirect(post.get_absolute_url())
    discussion.answer = None if discussion.answer_id == post.pk else post
    discussion.status = discussion.solved_status()
    discussion.updated_by = request.user
    discussion.save()
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def mark_duplicate(request, slug):
    """Close a topic as a duplicate of another one: group moderators only."""
    from urllib.parse import urlsplit

    from django.urls import Resolver404, resolve

    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not discussion.category.is_moderator(request.user):
        return HttpResponse(status=403)
    try:
        match = resolve(urlsplit(request.POST.get("original", "").strip()).path)
    except Resolver404:
        match = None
    original = None
    if match and match.view_name == "forum:discussion-detail":
        original = accessible_discussions(request.user).exclude(pk=discussion.pk).filter(
            slug=match.kwargs["slug"]).first()
    if original is None:
        messages.error(request, "Paste the link of another topic you can read.")
        return redirect(discussion.get_absolute_url())
    _lock(discussion)
    # A duplicate of a duplicate points to the end of the chain, as far as the chain runs through topics the
    # moderator can read; a chain back to this topic is refused.
    readable, seen = accessible_discussions(request.user), {discussion.pk}
    while original.duplicate_of_id and original.pk not in seen:
        seen.add(original.pk)
        following = readable.filter(pk=original.duplicate_of_id).first()
        if following is None:
            break
        original = following
    if original.pk == discussion.pk:
        messages.error(request, "That topic is itself closed as a duplicate of this one: reopen it first.")
        return redirect(discussion.get_absolute_url())
    discussion.duplicate_of, discussion.is_locked = original, True
    discussion.updated_by = request.user
    discussion.save()
    return redirect(discussion.get_absolute_url())


MODERATION_ACTIONS = {
    "pin": ("is_pinned", True, "Topic pinned."),
    "unpin": ("is_pinned", False, "Topic unpinned."),
    "close": ("is_locked", True, "Topic closed to new replies."),
    "reopen": ("is_locked", False, "Topic reopened."),
}


@login_required
@require_POST
def moderate_discussion(request, slug):
    """Pin or close a topic: group moderators and staff only."""
    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not discussion.category.is_moderator(request.user):
        return HttpResponse(status=403)
    action = MODERATION_ACTIONS.get(request.POST.get("action"))
    if action is None:
        return HttpResponseBadRequest("Unknown action.")
    field, value, message = action
    _lock(discussion)
    setattr(discussion, field, value)
    if field == "is_locked" and not value:
        # A reopened topic is no longer closed as a duplicate.
        discussion.duplicate_of = None
    discussion.updated_by = request.user
    discussion.save()
    messages.success(request, message)
    return redirect(discussion.get_absolute_url())


@login_required
@require_POST
def remove_record(request, slug, pk):
    """Unlink a GCD record from the topic: those who may edit it (utils.can_edit), so not a suspended author."""
    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not can_edit(request.user, discussion):
        return HttpResponse(status=403)
    DiscussionRecord.objects.filter(discussion=discussion, pk=pk).delete()
    return redirect(discussion.get_absolute_url())


class AuthorOrStaffMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Edit access for group moderators, staff and the content's author while they may post in its group;
    anyone else gets 403 Forbidden."""

    raise_exception = True

    def test_func(self):
        """Whether the user may edit the content (utils.can_edit)."""
        return can_edit(self.request.user, self.get_object())


class DiscussionUpdateView(AuthorOrStaffMixin, UpdateView):
    """Edit a topic's title and link it to more GCD records."""

    model = Discussion
    form_class = DiscussionEditForm
    slug_field = "slug"
    template_name = "forum/form.html"

    def get_queryset(self):
        """Published topics the user can access; any other topic is a 404."""
        return accessible_discussions(self.request.user)

    def get_form_kwargs(self):
        """Pass the user to the form, which records them as the one who linked the new records."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Save the topic with the user as its last editor, within the daily edit limit."""
        limit = edit_limit(self.request.user)
        if limit:
            form.add_error(None, limit)
            return self.form_invalid(form)
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class PostUpdateView(AuthorOrStaffMixin, UpdateView):
    """Edit the text of a post."""

    model = Post
    form_class = PostEditForm
    template_name = "forum/form.html"

    def get_queryset(self):
        """Published posts the user can access; any other post is a 404."""
        return accessible_posts(self.request.user)

    def form_valid(self, form):
        """Save the text and the user as last editor, and only them, so a change made meanwhile (a removal,
        a review) is not undone; then link the topic to the GCD records the text links to."""
        limit = edit_limit(self.request.user)
        if limit:
            form.add_error(None, limit)
            return self.form_invalid(form)
        form.instance.updated_by = self.request.user
        self.object = form.save(commit=False)
        self.object.save(update_fields=("content", "updated_by", "updated_at"))
        link_records(self.object)
        return redirect(self.get_success_url())

    def get_success_url(self):
        """Back to the edited post, on the page of the topic that holds it."""
        return self.object.get_absolute_url()


@login_required
@require_POST
def delete_discussion(request, slug):
    """Remove a topic: its author, group moderators and staff; it is kept, marked deleted by the user."""
    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not can_moderate(request.user, discussion):
        return HttpResponse(status=403)
    discussion.updated_by = request.user
    discussion.save(update_fields=("updated_by", "updated_at"))
    discussion.delete()
    _close_reports(request.user, discussion)
    messages.success(request, "Discussion removed.")
    return redirect("forum:index")


def _close_reports(user, content):
    """Mark the open reports about removed content handled by the user, when the user moderates its group;
    a removed topic's reports about its posts too, since they are gone with it. Reports about content its
    author removed stay open: the moderators still see them, with the content marked removed."""
    if not getattr(content, "discussion", content).category.is_moderator(user):
        return
    match = Q(content_type=ContentType.objects.get_for_model(content), object_id=content.pk)
    if isinstance(content, Discussion):
        match |= Q(content_type=ContentType.objects.get_for_model(Post),
                   object_id__in=Post.all_objects.filter(discussion=content).values("pk"))
    Report.objects.filter(match, status=Report.Status.OPEN).update(
        status=Report.Status.ACTIONED, reviewed_at=timezone.now(), reviewed_by=user)


@login_required
@require_POST
def delete_post(request, pk):
    """Remove a post: its author, group moderators and staff; it is kept, marked deleted by the user."""
    post = get_object_or_404(accessible_posts(request.user).select_related("discussion__category"), pk=pk)
    if not can_moderate(request.user, post):
        return HttpResponse(status=403)
    post.updated_by = request.user
    post.save(update_fields=("updated_by", "updated_at"))
    post.delete()
    _close_reports(request.user, post)
    if _is_htmx(request):
        response = HttpResponse()
        response["HX-Redirect"] = post.discussion.get_absolute_url()
        return response
    return redirect(post.discussion.get_absolute_url())


@login_required
@require_POST
def report_content(request, kind, pk):
    """Report a topic or a post to the moderators. A user has one report per content: reporting it again
    while the report is open changes nothing, and after it was handled opens it again with the new reason."""
    model = {"discussion": Discussion, "post": Post}.get(kind)
    if model is None:
        raise Http404
    queryset = accessible_posts(request.user) if model is Post else accessible_discussions(request.user)
    content = get_object_or_404(queryset, pk=pk)
    # The browser counts a line break as one character and sends two (CR LF): count it as the browser did.
    data = request.POST.copy()
    data["reason"] = data.get("reason", "").replace("\r\n", "\n")
    form = ReportForm(data)
    back = content.get_absolute_url() if kind == "discussion" else content.discussion.get_absolute_url()
    if not form.is_valid():
        messages.error(request, "The report was not sent: write a reason of at most 1000 characters. Your "
                                f"text: {data['reason'][:1000]}")
        return redirect(back)
    # One report per user and content: a new report of content already handled opens it again with the new reason.
    report, created = Report.objects.select_for_update().get_or_create(
        reporter=request.user, content_type=ContentType.objects.get_for_model(content), object_id=content.pk,
        defaults={"reason": form.cleaned_data["reason"]})
    if not created and report.status == Report.Status.OPEN:
        messages.info(request, "You have already reported this; the moderators have your report.")
    else:
        if not created:
            Report.objects.filter(pk=report.pk).update(
                reason=form.cleaned_data["reason"], status=Report.Status.OPEN, created_at=timezone.now(),
                reviewed_at=None, reviewed_by=None)
        messages.success(request, "Thank you. Your report was sent to the moderators.")
    return redirect(back)


def user_languages(user):
    """Language codes chosen in the user's GCD profile, the default filter of record searches."""
    from apps.indexer.models import Indexer

    indexer = Indexer.objects.filter(user_id=user.pk).first() if user.is_authenticated else None
    return list(indexer.languages.values_list("code", flat=True)) if indexer else []


@require_safe
def record_search(request):
    """A page of records of one type matching a name, to link to a topic without pasting links."""
    from .records import (COVER_TYPES, RECORD_TYPES, SEARCH_LIMIT, has_language, record_cover, record_details,
                          record_glyph, search_records)

    key = request.GET.get("type", "")
    query = request.GET.get("q", "")
    language = request.GET.get("lang", "")
    languages = user_languages(request.user) if language == "mine" else [language] if language else []
    raw_offset = request.GET.get("offset", "")
    offset = int(raw_offset) if raw_offset.isascii() and raw_offset.isdigit() and len(raw_offset) <= 6 else 0
    found, more = search_records(key, query, languages, offset=offset) if key in RECORD_TYPES else ([], False)
    covers = key in COVER_TYPES
    if key == "series":
        prefetch_related_objects(found, "first_issue__series", "first_issue__variant_of__series")
    results = [{"label": str(record), "details": record_details(key, record),
                "cover": record_cover(key, record) if covers else "",
                "url": request.build_absolute_uri(record.get_absolute_url())} for record in found]
    return render(request, "forum/_record_search.html", {
        "results": results, "more": more, "next_offset": offset + SEARCH_LIMIT, "offset": offset,
        "prefix": re.sub(r"[^\w-]", "", request.GET.get("prefix", "record"))[:60],
        "searched": len(query.strip()) >= 2, "filtered": bool(languages) and has_language(key),
        "issue_hint": key == "issue", "covers": covers, "glyph": record_glyph(key)})


@require_POST
def markdown_preview(request):
    """Preview of the message box: the text, up to the length a post may have, rendered as its post will
    show it."""
    return render(request, "forum/_markdown_preview.html",
                  {"content": request.POST.get("content", "")[:MAX_CONTENT]})


def _poll_discussion(request, slug):
    """The topic the user can access and its poll, or a 404."""
    discussion = get_object_or_404(
        accessible_discussions(request.user).select_related("category"), slug=slug)
    return discussion, get_object_or_404(Poll, discussion=discussion)


@login_required
@require_POST
def poll_vote(request, slug):
    """Vote, or change the vote, while the poll is open: users who can post in the group."""
    discussion, poll = _poll_discussion(request, slug)
    if not discussion.category.can_post(request.user):
        return HttpResponse("This poll is closed to you.", status=403)
    if not poll.is_open():
        messages.error(request, "The poll closed before your vote arrived.")
        return redirect(discussion.get_absolute_url())
    ids = [to_id(value) for value in request.POST.getlist("option") if to_id(value) is not None]
    chosen = list(poll.options.filter(pk__in=ids))
    if not chosen or (not poll.multiple and len(chosen) > 1):
        messages.error(request, "Choose at least one option." if poll.multiple else "Choose one option.")
        return redirect(discussion.get_absolute_url())
    with transaction.atomic():
        # Votes of one poll are saved one request at a time, and none after it closes.
        poll = Poll.objects.select_for_update().get(pk=poll.pk)
        if not poll.is_open():
            messages.error(request, "The poll closed before your vote arrived.")
            return redirect(discussion.get_absolute_url())
        PollVote.objects.filter(option__poll=poll, user=request.user).delete()
        PollVote.objects.bulk_create([PollVote(option=option, user=request.user) for option in chosen])
    messages.success(request, "Your vote is recorded. You can change it until the poll closes.")
    return redirect(f"{discussion.get_absolute_url()}#poll")


@login_required
@require_POST
def poll_close(request, slug):
    """Close the poll now: the topic's author, group moderators and staff."""
    discussion, poll = _poll_discussion(request, slug)
    if not _can_accept(request.user, discussion):
        return HttpResponse(status=403)
    if poll.closed_at is None:
        poll.closed_at = timezone.now()
        poll.save(update_fields=("closed_at",))
    return redirect(f"{discussion.get_absolute_url()}#poll")


@require_safe
def moderation(request):
    """Open reports about content in the groups the user moderates."""
    if not moderated_categories(request.user).exists():
        raise Http404
    reports = list(_open_reports(request.user).select_related("reporter__indexer")
                   .prefetch_related("content_object"))
    # The reported posts' and topics' authors, topics and groups, a query for each kind, not for each report.
    posts = [report.content_object for report in reports if isinstance(report.content_object, Post)]
    prefetch_related_objects(posts, "author__indexer", "discussion")
    prefetch_related_objects(
        [report.content_object for report in reports if isinstance(report.content_object, Discussion)]
        + [post.discussion for post in posts], "author__indexer", "category")
    for report in reports:
        content = report.content_object
        report.discussion = content if isinstance(content, Discussion) else content.discussion
        report.post = content if isinstance(content, Post) else None
    Notification.objects.filter(user=request.user, kind=Notification.Kind.REVIEW, read_at=None).update(
        read_at=timezone.now())
    context = _sidebar(request.user)
    context.update(reports=reports, held_posts=_awaiting_review(request.user), active_page="moderation")
    return render(request, "forum/moderation.html", context)


@login_required
@require_POST
def resolve_report(request, pk):
    """Remove the reported content, or dismiss the report: group moderators and staff."""
    report = get_object_or_404(Report, pk=pk)
    content = report.content_object
    discussion = content if isinstance(content, Discussion) else getattr(content, "discussion", None)
    # Permission first, so only moderators learn whether a report was handled.
    if discussion is None or not discussion.category.is_moderator(request.user):
        return HttpResponse(status=403)
    if report.status != Report.Status.OPEN:
        messages.info(request, "This report was already handled by another moderator.")
        return redirect("forum:moderation")
    action = request.POST.get("action")
    if action not in ("remove", "dismiss"):
        return HttpResponseBadRequest("Unknown action.")
    if action == "remove":
        if not content.is_deleted:
            content.updated_by = request.user
            content.save(update_fields=("updated_by", "updated_at"))
            content.delete()
        # Every open report about it, and about the posts of a removed topic, as removing it elsewhere does.
        _close_reports(request.user, content)
    else:
        Report.objects.filter(pk=report.pk).update(
            status=Report.Status.DISMISSED, reviewed_at=timezone.now(), reviewed_by=request.user)
    messages.success(request, "Content removed." if action == "remove" else "Report dismissed.")
    return redirect("forum:moderation")


@login_required
@require_POST
def review_post(request, pk):
    """Publish the post of a new member, or reject it: the group's moderators and staff.

    The topic is locked and the post checked again under the lock, so when two moderators decide at once
    the second finds the post handled and is told so, instead of rejecting a published post.
    """
    post = get_object_or_404(Post.all_objects.select_related("discussion__category"), pk=pk)
    discussion = post.discussion
    if not discussion.category.is_moderator(request.user):
        return HttpResponse(status=403)
    action = request.POST.get("action")
    if action not in ("approve", "reject"):
        return HttpResponseBadRequest("Unknown action.")
    _lock(discussion)
    if not Post.all_objects.select_for_update().filter(pk=post.pk, awaiting_review=True, is_deleted=False).exists():
        messages.info(request, "This post is no longer waiting for review: another moderator has handled it.")
        return redirect("forum:moderation")
    post.refresh_from_db()
    new_topic = discussion.awaiting_review
    with transaction.atomic():
        for content in ([discussion] if new_topic else []) + [post]:
            content.updated_by = request.user
            if action == "approve":
                content.awaiting_review = False
                content.save(update_fields=("awaiting_review", "updated_by", "updated_at"))
            else:
                content.save(update_fields=("updated_by", "updated_at"))
                content.delete()
        Notification.objects.filter(post=post, kind=Notification.Kind.REVIEW).update(read_at=timezone.now())
        if action == "approve":
            # As in Discourse, a held post appears when it is approved: at the end of the topic, which moves
            # up in the lists. Readers who had already read later posts are not shown it as unread (a read
            # mark is the highest post id read, and lowering it would mark those later posts unread too);
            # its topic's followers are notified of it.
            Post.all_objects.filter(pk=post.pk).update(created_at=timezone.now())
            discussion.update_counters()
            publish(post, discussion.records.all() if new_topic else ())
    messages.success(request, "Post published." if action == "approve" else "Post rejected.")
    return redirect("forum:moderation")


@require_safe
def attachment(request, pk, name):
    """An attachment, for those who can read its post; moderators also see posts under review."""
    item = get_object_or_404(Attachment.objects.select_related("post__discussion__category"), pk=pk)
    post = item.post
    readable = accessible_posts(request.user).filter(pk=post.pk).exists() or (
        post.awaiting_review and not post.is_deleted and post.discussion.category.is_moderator(request.user))
    if not readable and not request.user.is_authenticated and name == item.name:
        return register_required(request)
    if not readable or name != item.name:
        raise Http404
    shown = item.preview if request.GET.get("preview") and item.preview else item.file
    try:
        content = shown.open("rb")
    except OSError:
        # A folder not restored after a move: log it, and answer each reader with a plain 404.
        logger.warning("Forum: the file %s of attachment %s cannot be read", shown.name, item.pk,
                       exc_info=True)
        raise Http404
    content_type = item.content_type
    if shown is item.preview:
        content_type = "image/png" if shown.name.endswith(".png") else "image/jpeg"
    response = FileResponse(content, content_type=content_type,
                            as_attachment=not item.is_image, filename=item.name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    # A file never changes: the reader's browser keeps it for a day, and no shared cache keeps it at all,
    # so a removed post's files are not served from a proxy.
    response["Cache-Control"] = "private, max-age=86400"
    return response


@require_safe
def post_history(request, pk):
    """The earlier versions of an edited post, as in Discourse; editors are named, IPs are not."""
    post = get_object_or_404(accessible_posts(request.user).select_related("author__indexer", "discussion__category"),
                             pk=pk)
    # Text edited out stays out for readers, as in Discourse with edit history not public.
    if not can_moderate(request.user, post):
        raise Http404
    revisions = ContentRevision.objects.filter(
        content_type=ContentType.objects.get_for_model(Post), object_id=post.pk
    ).select_related("actor__indexer").order_by("created_at", "pk")
    versions = [{"content": revision.after.get("content", ""), "at": revision.created_at,
                 "by": display_name(revision.actor)}
                for revision in revisions if revision.after.get("content") != revision.before.get("content")]
    return render(request, "forum/post_history.html",
                  {"post": post, "discussion": post.discussion, "versions": list(reversed(versions))})


@login_required
@require_POST
def link_change(request, slug):
    """Link a database change (changeset) to the topic; an approved one marks the topic fixed."""
    from .activity import check_fix
    from .database import parse_changeset

    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    changeset = parse_changeset(request.POST.get("changeset", ""))
    if changeset is None:
        messages.error(request, "Paste the number or the link of a change (changeset).")
        return redirect(discussion.get_absolute_url())
    if not can_link_change(request.user, discussion, changeset):
        return HttpResponse(status=403)
    else:
        _lock(discussion)
        DiscussionChange.objects.get_or_create(
            discussion=discussion, changeset=changeset, defaults={"linked_by": request.user})
        if check_fix(discussion):
            messages.success(request, f"Change {changeset.pk} is approved: the topic is marked fixed.")
    return redirect(f"{discussion.get_absolute_url()}#database")


@login_required
@require_POST
def unlink_change(request, slug, pk):
    """Unlink a database change from the topic: the user who linked it, group moderators and staff."""
    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    link = get_object_or_404(DiscussionChange, discussion=discussion, pk=pk)
    if not (link.linked_by_id == request.user.pk or discussion.category.is_moderator(request.user)):
        return HttpResponse(status=403)
    from .activity import check_fix

    _lock(discussion)
    link.delete()
    if discussion.fixed_by_id == link.changeset_id:
        # The topic was marked fixed by this change: it is no longer, and is open again unless an answer or
        # a consensus solved it (Discussion.solved_status); another approved linked change marks it again.
        discussion.fixed_by = None
        Discussion.all_objects.filter(pk=discussion.pk, fixed_by=link.changeset_id).update(
            fixed_by=None, status=discussion.solved_status())
        discussion.refresh_from_db()
        check_fix(discussion)
        messages.success(request, f"Change {link.changeset_id} unlinked: the topic is no longer marked fixed by it.")
    return redirect(f"{discussion.get_absolute_url()}#database")


@require_safe
def similar_topics(request):
    """Topics like the one being written: same records first, then titles sharing words."""
    from .records import STOP_WORDS, records_in_text

    title = request.GET.get("title", "")[:200]
    words = [word for word in re.findall(r"\w+", title.lower()) if len(word) > 3 and word not in STOP_WORDS][:8]
    linked = records_in_text(request.GET.get("content", ""))
    topics = accessible_discussions(request.user).select_related("category")
    found = []
    if linked:
        match = Q()
        for key, found_record in linked:
            match |= Q(records__content_type=record_content_type(key), records__object_id=found_record.pk)
        found = list(topics.filter(match).distinct().order_by("-last_activity")[:5])
    if words and len(found) < 5:
        score = sum((Case(When(title__icontains=word, then=1), default=0) for word in words), Value(0))
        found += list(topics.exclude(pk__in=[topic.pk for topic in found]).annotate(score=score)
                      .filter(score__gte=min(2, len(words))).order_by("-score", "-last_activity")[:5 - len(found)])
    return render(request, "forum/_similar_topics.html", {"topics": found})


def _lock(discussion):
    """Lock the topic's row until the request ends and reload it, so the checks made on it hold until the
    request commits: two clicks, or two coordinators, then act one after the other."""
    Discussion.lock(discussion.pk)
    discussion.refresh_from_db()
    return discussion


def _coordinator_discussion(request, slug):
    """The topic, for its group's moderators (coordinators) and staff only; anyone else gets a 403."""
    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    if not discussion.category.is_moderator(request.user):
        raise PermissionDenied
    return discussion


@login_required
@require_POST
def link_agenda(request, slug):
    """Coordinators link the topic to its agenda item and ballot in the voting system."""
    from .procedure import agenda_items_for, parse_ballot

    discussion = _lock(_coordinator_discussion(request, slug))
    item = request.POST.get("agenda_item", "")
    if to_id(item) is None:
        discussion.agenda_item = None
    elif to_id(item) == discussion.agenda_item_id:
        pass
    else:
        discussion.agenda_item = agenda_items_for(discussion.category).filter(pk=to_id(item)).first()
        if discussion.agenda_item is None:
            messages.error(request, "Choose one of the group's open agenda items.")
            return redirect(discussion.get_absolute_url())
        # One topic per item, as when a topic is started from the agenda: the group's agenda shows one.
        if Discussion.all_objects.filter(agenda_item=discussion.agenda_item, is_deleted=False).exclude(
                pk=discussion.pk).exists():
            messages.error(request, "That agenda item already has a discussion: link this topic to another "
                                    "item, or close it as a duplicate of that discussion.")
            return redirect(discussion.get_absolute_url())
    ballot_text = request.POST.get("ballot", "").strip()
    discussion.ballot = parse_ballot(ballot_text) if ballot_text else None
    if ballot_text and discussion.ballot is None:
        messages.error(request, "Paste the number or the link of a ballot (/voting/ballot/<number>/).")
        return redirect(discussion.get_absolute_url())
    discussion.updated_by = request.user
    discussion.save()
    return redirect(f"{discussion.get_absolute_url()}#procedure")


@login_required
@require_POST
def seek_consensus(request, slug):
    """Seek consensus after three days of discussion, once, with a post saying so: coordinators and staff."""
    from .procedure import can_seek_consensus

    discussion = _lock(_coordinator_discussion(request, slug))
    if not can_seek_consensus(discussion):
        return HttpResponseBadRequest("Consensus can be sought after three days of discussion, once.")
    discussion.consensus_sought_at, discussion.consensus_sought_by = timezone.now(), request.user
    discussion.updated_by = request.user
    discussion.save()
    post = Post.objects.create(
        discussion=discussion, author=request.user, created_by=request.user, updated_by=request.user,
        ip_address=get_client_ip(request),
        content="**Seeking consensus.** If nobody objects within one week and one day, this item passes "
                "by consensus. To object, use “Object” on the topic page.")
    publish(post)
    return redirect(f"{discussion.get_absolute_url()}#procedure")


@login_required
@require_POST
def object_to_consensus(request, slug):
    """Dissent while consensus is sought; the reason becomes a post, and the item goes to a vote."""
    from .procedure import consensus_state

    discussion = get_object_or_404(accessible_discussions(request.user).select_related("category"), slug=slug)
    limit = posting_limit(request.user)
    _lock(discussion)
    consensus = consensus_state(discussion)
    if not discussion.category.can_post(request.user):
        return HttpResponse(status=403)
    reason = request.POST.get("reason", "").strip()[:2000]
    if consensus is None or consensus["state"] == "passed":
        messages.error(request, "The consensus step is over, so the objection was not sent; reply to the topic "
                                f"instead. Your text: {reason}")
        return redirect(discussion.get_absolute_url())
    if not reason:
        messages.error(request, "Say what you object to.")
        return redirect(discussion.get_absolute_url())
    # An objection whose post was removed is withdrawn; the member may object again.
    Objection.objects.filter(discussion=discussion, user=request.user, post__is_deleted=True).delete()
    if Objection.objects.filter(discussion=discussion, user=request.user).exists():
        messages.error(request, "You already objected; reply to the topic to add more.")
        return redirect(discussion.get_absolute_url())
    if limit:
        messages.error(request, limit)
        return redirect(discussion.get_absolute_url())
    if needs_review(request.user, discussion.category):
        # An objection is published at once and stops the consensus, so it is not a new member's first post.
        messages.error(request, "A new member's first message is read by a moderator first: reply to the topic "
                                "with your objection, and the coordinators will see it.")
        return redirect(discussion.get_absolute_url())
    post = Post.objects.create(
        discussion=discussion, author=request.user, created_by=request.user, updated_by=request.user,
        ip_address=get_client_ip(request), content=f"**Objection:** {reason}")
    Objection.objects.create(discussion=discussion, user=request.user, post=post)
    publish(post)
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def declare_consensus(request, slug):
    """Declare the item passed by consensus, after a week and a day without objections.

    Coordinators and staff only; the topic is marked resolved, and a post announces the result.
    """
    from .procedure import consensus_state

    discussion = _lock(_coordinator_discussion(request, slug))
    consensus = consensus_state(discussion)
    if consensus is None or consensus["state"] != "ready":
        return HttpResponseBadRequest("Consensus can be declared after one week and one day without objections.")
    discussion.consensus_passed_at = timezone.now()
    discussion.status = Discussion.Status.RESOLVED
    discussion.updated_by = request.user
    discussion.save()
    post = Post.objects.create(
        discussion=discussion, author=request.user, created_by=request.user, updated_by=request.user,
        ip_address=get_client_ip(request), content="**Passed by consensus.**")
    publish(post)
    return redirect(f"{discussion.get_absolute_url()}#procedure")
